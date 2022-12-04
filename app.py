from flask import Flask,render_template,send_from_directory,url_for
from flask_uploads import UploadSet,IMAGES,configure_uploads
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired,FileAllowed
from wtforms import SubmitField
from flask_sqlalchemy import SQLAlchemy
from serializer import *
from flask import jsonify
from datetime import datetime
import os

from flask import request
from werkzeug.utils import secure_filename

import random

from line_notify import lineNotifyMessage

from roboflow import Roboflow
Bee_rf = Roboflow(api_key="test")
Bee_project = Bee_rf.workspace().project("honey-bee-detection-model-zgjnb")
Bee_model = Bee_project.version(2).model

Hornet_rf = Roboflow(api_key="test")
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
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
app.config["UPLOADED_PHOTOS_DEST"] = "uploads"
app.config["PREDICT_PHOTOS_DEST"] = "predict"
app.config["SECRET_KEY"] = "asldfkjlj"

LINE_TOKEN ='test' #NCHU

# initialize the app with the extension
db.init_app(app)

photos = UploadSet('photos',IMAGES)
configure_uploads(app,photos)

class UploadForm(FlaskForm):
    photo = FileField(
        validators=[
            FileAllowed(photos,'Only images are allowed'),
            FileRequired('File field should not be empty')
        ]
    )
    submit = SubmitField('Upload')

with app.app_context():
    print('初始化資料庫')
    #db.drop_all()
    db.create_all()


@app.route("/", methods=["GET", "POST"])
def upload_image():
    form = UploadForm()
    if form.validate_on_submit():
        filename = photos.save(form.photo.data)
        path = app.config["UPLOADED_PHOTOS_DEST"]+"/"+filename
        file_url = url_for('get_file',filename="detect.jpg")  
        dectectAndNotify(path)
        os.remove(path)
    else:
        file_url = None
    return render_template('index.html',form=form,file_url=file_url)

@app.route("/predict/<filename>", methods=["GET", "POST"])
def get_file(filename):
    return send_from_directory(app.config["PREDICT_PHOTOS_DEST"] ,filename)

@app.route("/reocrd/create", methods=["GET", "POST"])
def create():
    try:
        item = Reocrd(
            HiveID = "2",
            NumberOfBees = "3",
            HasHornets="N"
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


#取得蜂箱編號
@app.route('/hiveNumber', methods=['GET'])
def getHiveIDs():
    HiveIDs =db.session.execute(db.select(Reocrd.HiveID).distinct())
    print(HiveIDs)
    return jsonify([*map(HiveID_serializer,HiveIDs)])


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

@app.route('/test', methods=['POST'])
def fileUpload():
    file = request.files['my_filename'] 
    filename = secure_filename(file.filename)
    file.save(app.config["UPLOADED_PHOTOS_DEST"]+"/"+filename)
    dectectAndNotify("uploads/"+filename)
    response="Whatever you wish too return"
    return response

def dectectAndNotify(path):
    beens = Bee_model.predict(path, confidence=40, overlap=30).json()
    numberOfBees =  len([x for x in beens['predictions'] if x['class'] == 'bee'])
    hiveID = random.randint(1,5)
    hornets = Hornet_model.predict(path, confidence=40, overlap=30).json()
    hasHornets = 'Y' if len([x for x in hornets['predictions'] if x['class'] == 'Asian Hornet']) > 0 else 'N'
    if numberOfBees>0:
        AddData(hiveID,numberOfBees,hasHornets)
    if hasHornets == 'Y':
        Hornet_model.predict(path, confidence=40, overlap=30).save("prediction.jpg")
        #lineNotifyMessage('注意!!疑似虎頭蜂出沒',"predict/detect.jpg",LINE_TOKEN)
    #Bee_model.predict(path, confidence=40, overlap=30).save("predict/detect.jpg")
    #lineNotifyMessage('注意!!疑似虎頭蜂出沒',"predict/detect.jpg",LINE_TOKEN)

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
