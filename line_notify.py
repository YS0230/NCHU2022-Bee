import requests

def lineNotifyMessage(msg,imgPath,token=''):
    if token=='':
        token = 'test'
    # HTTP 標頭參數與資料
    headers = { "Authorization": "Bearer " + token }

    # 要發送的訊息
    data = { 'message': msg }

    # 要傳送的圖片檔案
    try:
        image = open(imgPath, 'rb')
        
    except:
        return 'can not open img'
    files = { 'imageFile': image }
    # 以 requests 發送 POST 請求
    r = requests.post("https://notify-api.line.me/api/notify",
        headers = headers, data = data, files = files)
    
    return r.status_code