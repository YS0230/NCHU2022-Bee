from flask import Flask,jsonify,make_response
from flask_sqlalchemy import SQLAlchemy
from serializer import *
from datetime import datetime
import os
from sqlalchemy import desc
from flask import request
from werkzeug.utils import secure_filename
import random
from line_notify import lineNotifyMessage
from roboflow import Roboflow
from flask_cors import CORS


Bee_rf = Roboflow(api_key=os.getenv('api_key'))
Bee_project = Bee_rf.workspace().project("honey-bee-detection-model-zgjnb")
Bee_model = Bee_project.version(2).model

Hornet_rf = Roboflow(api_key=os.getenv('api_key'))
Hornet_project = Hornet_rf.workspace().project("bee-d4yoh")
Hornet_model = Hornet_project.version(5).model


# create the extension
db = SQLAlchemy()

class Reocrd(db.Model):
    id = db.Column(db.Integer, primary_key=True)            #流水號
    HiveID = db.Column(db.String, nullable=False)           #蜂箱編號
    NumberOfBees = db.Column(db.String, nullable=False)     #蜜蜂數量
    HasHornets = db.Column(db.String, nullable=False)       #是否有虎頭
    CreateTime = db.Column(db.DateTime, default=datetime.now, nullable=False) #監測時間

# create the app
app = Flask(__name__)
# configure the SQLite database, relative to the app instance folder
if os.getenv('DATABASE_URL'):
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
else:
    SQLALCHEMY_DATABASE_URI = "sqlite:///project.db"

if os.getenv('SECRET_KEY'):
    SECRET_KEY = os.getenv('SECRET_KEY')
else:
    SECRET_KEY = "asldfkjlj"

if os.getenv('TOKEN'):
    app.config["TOKEN"] = os.getenv('TOKEN')
else:
    app.config["TOKEN"] = "8888"


app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SECRET_KEY"] = SECRET_KEY
app.config["LINE_TOKEN"] = os.getenv('LINE_TOKEN') #NCHU
app.config["UPLOADED_PHOTOS_DEST"] = "uploads"
app.config["PREDICT_PHOTOS_DEST"] = "predict"

# initialize the app with the extension
db.init_app(app)
CORS(app)

with app.app_context():
    print('初始化資料庫')
    #db.drop_all()
    db.create_all()


@app.route("/", methods=["GET", "POST"])
def root():
    HiveIDs =db.session.execute(db.select(Reocrd.HiveID).distinct())
    return jsonify([*map(HiveID_serializer,HiveIDs)])


#取得蜂箱編號
@app.route('/hiveNumber', methods=['GET'])
def getHiveIDs():
    HiveIDs =db.session.execute(db.select(Reocrd.HiveID).distinct())
    return jsonify([*map(HiveID_serializer,HiveIDs)])

#取得蜂箱資料
@app.route('/hiveData/<string:HiveID>', methods=['GET'])
def getHiveDatas(HiveID):
    
    limit = int(str(request.args.get("limit",'0')))
    datas = []
    if(limit):
        datas = Reocrd.query.filter_by(HiveID=HiveID).order_by(desc(Reocrd.CreateTime)).limit(limit)
    else:
        datas =Reocrd.query.filter_by(HiveID=HiveID).order_by(desc(Reocrd.CreateTime)).all()
    return jsonify([*map(Reocrd_serializer,datas)])

def HiveID_serializer(Reocrd):
    return{'HiveID' : Reocrd.HiveID}

def Reocrd_serializer(Reocrd):
    return{
        'id' : Reocrd.id, 
        'HiveID' : Reocrd.HiveID,
        'NumberOfBees' : Reocrd.NumberOfBees,
        'HasHornets' : Reocrd.HasHornets,
        'CreateTime' : Reocrd.CreateTime
    }


@app.route('/ReactUpload', methods=['POST'])
def fileUpload():
    if 'file' in request.files:
        file = request.files['file']   
        ID = None  
        if 'ID' in request.files:    
            ID = request.files['ID'] 
            print('test2'+ID)
        filename = secure_filename(file.filename)
        if not os.path.exists(app.config["UPLOADED_PHOTOS_DEST"]):
            os.mkdir(app.config["UPLOADED_PHOTOS_DEST"])
        file.save(app.config["UPLOADED_PHOTOS_DEST"]+"/"+filename)
        return dectectAndNotify("uploads/"+filename,ID)
    else:
        return "Please package the file into an object ['file':source]"

def dectectAndNotify(path,ID):
    beens = Bee_model.predict(path, confidence=40, overlap=30).json()
    numberOfBees =  len([x for x in beens['predictions'] if x['class'] == 'bee'])
    hiveID = ID
    if hiveID is None:
        hiveID = random.randint(1,5)
    hornets = Hornet_model.predict(path, confidence=40, overlap=30).json()
    hasHornets = 'Y' if len([x for x in hornets['predictions'] if x['class'] == 'Asian Hornet']) > 0 else 'N'
    res = "uuload success"
    if numberOfBees>0:
        res = AddData(hiveID,numberOfBees,hasHornets)
    if hasHornets == 'Y':
        if not os.path.exists(app.config["PREDICT_PHOTOS_DEST"]):
            os.mkdir(app.config["PREDICT_PHOTOS_DEST"])
        Hornet_model.predict(path, confidence=40, overlap=30).save(app.config["PREDICT_PHOTOS_DEST"] +"/prediction.jpg")
        lineNotifyMessage('注意!!第'+str(hiveID)+'號蜂箱疑似虎頭蜂出沒',"predict/prediction.jpg",app.config["LINE_TOKEN"] )
    return res,200

def AddData(hiveID,numberOfBees,hasHornets):
    try:
        item = Reocrd(
            HiveID = hiveID,
            NumberOfBees = numberOfBees,
            HasHornets=hasHornets
        )
        db.session.add(item)
        db.session.commit()
    except Exception as e:
        print(e)
        responseObject = {
            'status': 'fail',
            'message': str(e)
        }
        return make_response(jsonify(responseObject)), 500 
    return jsonify(Reocrd_serializer(item))

if __name__ == '__main__':
    app.run(debug=True)
