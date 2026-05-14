from flask import Flask, render_template, request, make_response, jsonify
from datetime import datetime

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import requests
from bs4 import BeautifulSoup

# --- Firebase 初始化邏輯 ---
if not firebase_admin._apps:
    if os.path.exists('serviceAccountKey.json'):
        # 本地環境
        cred = credentials.Certificate('serviceAccountKey.json')
    else:
        # 雲端環境 (Vercel)
        firebase_config = os.getenv('FIREBASE_CONFIG')
        if firebase_config:
            cred_dict = json.loads(firebase_config)
            cred = credentials.Certificate(cred_dict)
        else:
            raise ValueError("找不到 Firebase 配置環境變數")
    firebase_admin.initialize_app(cred)

db = firestore.client()
app = Flask(__name__)

# --- 路由設定 ---

@app.route("/")
def index():
    link = "<h1>歡迎進入劉宇崴的網站20260409</h1>"
    link += "<a href=/mis>課程</a><hr>"
    link += "<a href=/today>現在日期時間</a><hr>"
    link += "<a href=/me>關於我</a><hr>"
    link += "<a href='/welcome?u=宇崴&d=靜宜資管&c=資訊管理導論'>Get傳值</a><hr>"
    link += "<a href=/account>Post傳值(帳密)</a><hr>"
    link += "<a href=/math>次方與根號計算</a><hr>"
    link += "<a href=/read>讀取Firestore資料</a><hr>"
    link += "<a href=/read2>讀取Firestore資料(固定關鍵字:楊)</a><hr>"
    link += "<a href=/read3>讀取Firestore資料(動態輸入關鍵字)</a><hr>"
    link += "<a href=/spider>爬取子青老師本學期課程</a><hr>"
    link += "<a href=/movie1>爬取即將上映電影</a><hr>"
    link += "<a href=/spidermovie>讀取開眼電影即將上映影片，寫入Firestore</a><hr>"
    link += "<a href=/searchmovie>查詢資料庫符合電影</a><hr>"
    link += "<a href=/road>台中市十大肇事路口</a><hr>"
    link += "<a href=/weather>查詢縣市顯示目前天氣及降雨機率</a><hr>"
    link += "<a href=/rate>本週新片進DB</a><hr>"
    link += "<a href=/webhook>本週新片機器人</a><hr>"
    return link

@app.route("/webhook", methods=["POST"])
def webhook():
    # 建立 request 物件
    req = request.get_json(force=True)
    
    # 取得 Dialogflow 傳來的 action
    action = req.get("queryResult", {}).get("action")
    
    # 設定一個預設的回覆內容，避免 action 不符時 info 變數未定義而報錯
    info = "我是劉宇崴設計的機器人，目前無法辨識您的請求。"

    if action == "rateChoice":
        rate = req["queryResult"]["parameters"]["rate"]
        info = "我是劉宇崴設計的機器人，您選擇的電影分級是：" + rate + "，相關電影：\n"

        # 資料庫查詢必須縮排在 if 條件式內部
        db = firestore.client()
        collection_ref = db.collection("本週新片含分級")
        docs = collection_ref.get()
        
        result = ""
        for doc in docs:
            # 避免使用 python 內建字詞 dict 當作變數名，改用 movie_data
            movie_data = doc.to_dict()
            
            # 確保欄位存在再做比對，避免 KeyError
            if "rate" in movie_data and rate in movie_data["rate"]:
                result += "片名：" + movie_data.get("title", "未知片名") + "\n"
                # result += "介紹：" + movie_data.get("hyperlink", "") + "\n\n"
        
        # 如果找不到相關電影，給予友善提示
        if result == "":
            result = "目前資料庫沒有這個分級的電影喔！\n"
            
        info += result

    return make_response(jsonify({"fulfillmentText": info}))

@app.route("/rate")
def rate():
    #本週新片
    url = "https://www.atmovies.com.tw/movie/new/"
    Data = requests.get(url)
    Data.encoding = "utf-8"
    sp = BeautifulSoup(Data.text, "html.parser")
    lastUpdate = sp.find(class_="smaller09").text[5:]
    print(lastUpdate)
    print()

    result=sp.select(".filmList")

    for x in result:
        title = x.find("a").text
        introduce = x.find("p").text

        movie_id = x.find("a").get("href").replace("/", "").replace("movie", "")
        hyperlink = "http://www.atmovies.com.tw/movie/" + movie_id
        picture = "https://www.atmovies.com.tw/photo101/" + movie_id + "/pm_" + movie_id + ".jpg"

        r = x.find(class_="runtime").find("img")
        rate = ""
        if r != None:
            rr = r.get("src").replace("/images/cer_", "").replace(".gif", "")
            if rr == "G":
                rate = "普遍級"
            elif rr == "P":
                rate = "保護級"
            elif rr == "F2":
                rate = "輔12級"
            elif rr == "F5":
                rate = "輔15級"
            else:
                rate = "限制級"

        t = x.find(class_="runtime").text

        t1 = t.find("片長")
        t2 = t.find("分")
        showLength = t[t1+3:t2]

        t1 = t.find("上映日期")
        t2 = t.find("上映廳數")
        showDate = t[t1+5:t2-8]

        doc = {
            "title": title,
            "introduce": introduce,
            "picture": picture,
            "hyperlink": hyperlink,
            "showDate": showDate,
            "showLength": int(showLength),
            "rate": rate,
            "lastUpdate": lastUpdate
        }

        db = firestore.client()
        doc_ref = db.collection("本週新片含分級").document(movie_id)
        doc_ref.set(doc)
    return "本週新片已爬蟲及存檔完畢，網站最近更新日期為：" + lastUpdate

@app.route("/weather", methods=["GET", "POST"])
def weather():
    if request.method == "POST":
        city = request.values.get("keyword")
        # 處理台灣/臺灣字體統一問題
        city = city.replace("台", "臺")
        
        # 氣象署 API URL (這裡使用你提供的 Authorization key)
        url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization=rdec-key-123-45678-011121314&format=JSON&locationName=" + city

        try:
            data = requests.get(url)
            json_data = data.json()
            
            # 檢查是否有回傳縣市資料
            if not json_data["records"]["location"]:
                result = f"<h2>抱歉，找不到『{city}』的氣象資料。</h2>"
                result += "<p>請確保輸入正確的縣市名稱（例如：臺中市、宜蘭縣）。</p>"
            else:
                location = json_data["records"]["location"][0]
                city_name = location["locationName"]
                
                # 取得天氣狀態與降雨機率 (索引 0 為天氣現象, 索引 1 為降雨機率)
                weather_info = location["weatherElement"][0]["time"][0]["parameter"]["parameterName"]
                rain_chance = location["weatherElement"][1]["time"][0]["parameter"]["parameterName"]
                
                result = f"<h2>{city_name} 最新天氣預報</h2>"
                result += f"<p style='font-size:1.2em;'>當前天氣狀況：<strong>{weather_info}</strong></p>"
                result += f"<p style='font-size:1.2em;'>降雨機率：<strong>{rain_chance}%</strong></p>"
        
        except Exception as e:
            result = f"<h2>連線發生錯誤</h2><p>{str(e)}</p>"

        return result + "<br><a href='/weather'>重新查詢</a> | <a href='/'>回首頁</a>"
        
    else:
        # GET 請求：顯示輸入框
        html = """
        <h2>氣象預報查詢</h2>
        <form action="/weather" method="POST">
            請輸入查詢縣市 (如：臺中市)：
            <input type="text" name="keyword" placeholder="例如：臺中市" required>
            <button type="submit">查詢</button>
        </form>
        <br><a href="/">回首頁</a>
        """
        return html


@app.route("/road")
def road():
    Result="<h1>台中市十大肇事路口(113年10月) 作者:劉宇崴</h1><br>"
    url = "https://datacenter.taichung.gov.tw/swagger/OpenData/a1b899c0-511f-4e3d-b22b-814982a97e41"
    headers={'User-Agent':'Mozilla/5.0'}
    Data = requests.get(url,headers=headers, timeout=10)
    #print(Data.text)
    JsonData = json.loads(Data.text)
    for item in JsonData:
        Result+=item["路口名稱"]+",原因:"+item["主要肇因"]+",件數:"+item["總件數"]+"<br>"
        
    return Result

@app.route("/searchmovie", methods=["GET", "POST"])
def searchmovie():
    if request.method == "POST":
        # 抓取表單裡面 name="keyword" 的欄位當作關鍵字
        keyword = request.values.get("keyword")
        Result = f"<h2>查詢電影關鍵字：{keyword}</h2>"
        
        db = firestore.client()
        collection_ref = db.collection("電影2B")
        docs = collection_ref.get()
        
        found = False
        
        for doc in docs:
            movie_data = doc.to_dict()
            # 檢查關鍵字是否包含在片名中
            if keyword in movie_data.get("title", ""): 
                found = True
                # 【修正這裡】：使用 doc.id 來取得 Firestore 的文件 ID 作為電影編號
                Result += f"<b>編號：</b>{doc.id}<br>"
                Result += f"<b>片名：</b>{movie_data.get('title', '未知')}<br>"
                # 顯示海報圖片
                Result += f"<b>海報：</b><br><img src='{movie_data.get('picture', '')}' style='width:150px;'><br>"
                # 將介紹頁轉為可點擊的超連結
                Result += f"<b>介紹頁：</b><a href='{movie_data.get('hyperlink', '#')}' target='_blank'>點我查看</a><br>"
                Result += f"<b>上映日期：</b>{movie_data.get('showDate', '未知')}<br><hr>"
        
        if not found:
            Result += "抱歉，查無此關鍵字之電影資料。<br>"

        return Result + "<br><a href='/searchmovie'>重新查詢</a> | <a href='/'>回首頁</a>"
        
    else:
        html="""
        <h2>電影查詢</h2>
        <form action="/searchmovie" method="POST">
            請輸入電影片名關鍵字：
            <input type="text" name="keyword" required>
            <button type="submit">查詢</button>
        </form>
        <br><a href="/">回首頁</a>
        """
        # GET 請求時，顯示輸入表單
        return html

@app.route("/spidermovie")
def spidermovie():
    Result=""
    db = firestore.client()

    url = "http://www.atmovies.com.tw/movie/next/"
    Data = requests.get(url)
    sp = BeautifulSoup(Data.text, "html.parser")
    Data.encoding = "utf-8"

    lastupdate=sp.find(class_="smaller09").text.replace("更新時間：","")

    result=sp.select(".filmListAllX li")

    total = 0
    for item in result:
        total += 1
        title = item.find(class_="filmtitle").text
        picture = "https://www.atmovies.com.tw"+item.find("img").get("src")
        hyperlink = "https://www.atmovies.com.tw"+item.find("a").get("href")
        movie_id= item.find("a").get("href").replace("/movie/","").replace("/","")
        showDate=item.find(class_="runtime").text[5:15]

        doc = {
            "title": title,
            "picture": picture,
            "hyperlink": hyperlink,
            "showDate": showDate,
            "lastupdate": lastupdate
        }

        doc_ref = db.collection("電影2B").document(movie_id)
        doc_ref.set(doc)

    Result+="網站更新日期"+lastupdate+"<br>"
    Result+="總共爬取"+str(total)+"部電影到資料庫"+"<br>"
    return Result

@app.route("/mis")
def course():
    return "<h1>資訊管理導論</h1><a href=/>返回首頁</a>"

@app.route("/today")
def today():
    now = datetime.now()
    return render_template("today.html", datetime=str(now))

@app.route("/me")
def me():    
    return render_template("mis2B.html")

@app.route("/welcome", methods=["GET"])
def welcome():
    user = request.values.get("u")
    d = request.values.get("d")
    c = request.values.get("c")
    return render_template("welcome.html", name=user, dep=d, course=c)

@app.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        user = request.form["user"]
        pwd = request.form["pwd"]
        return f"您輸入的帳號是：{user}; 密碼為：{pwd} <br><a href='/'>回首頁</a>"
    return render_template("account.html")

@app.route("/math", methods=["GET", "POST"])
def math():
    result = ""
    if request.method == "POST":
        try:
            x = float(request.form.get("x"))
            y = float(request.form.get("y"))
            opt = request.form.get("opt")
            if opt == "∧":
                result = x ** y
            elif opt == "√":
                result = "錯誤：不能開 0 次方根" if y == 0 else x ** (1 / y)
        except:
            result = "請輸入有效數字"
    return render_template("math.html", final_result=result)

@app.route("/read")
def read():
    Result = "<h2>所有老師資料：</h2>"
    collection_ref = db.collection("靜宜資管")    
    docs = collection_ref.order_by("lab", direction=firestore.Query.DESCENDING).get()    
    for doc in docs:         
        Result += str(doc.to_dict()) + "<br><hr>"    
    return Result + "<a href=/>回首頁</a>"

@app.route("/read2")
def read2():
    Result = "<h2>搜尋關鍵字：楊</h2>"
    keyword = "楊"
    collection_ref = db.collection("靜宜資管")    
    docs = collection_ref.get()    
    found = False
    for doc in docs:
        teacher = doc.to_dict()
        if keyword in teacher.get("name", ""):         
            Result += str(teacher) + "<br>"
            found = True
    if not found:
        Result += "抱歉，查無資料"
    return Result + "<br><a href=/>回首頁</a>"

# --- 修改後的 read3：結合表單輸入與 Firestore 查詢 ---
@app.route("/read3", methods=["GET", "POST"])
def read3():
    if request.method == "POST":
        # 抓取 account.html 裡面 name="user" 的欄位當作關鍵字
        keyword = request.values.get("keyword")
        Result = f"<h2>查詢姓名關鍵字：{keyword}</h2>"
        db=firestore.client()
        collection_ref = db.collection("靜宜資管")
        docs = collection_ref.get()
        
        found = False
        for doc in docs:
            teacher = doc.to_dict()
            if keyword in teacher.get("name", ""):
                Result += f"老師：{teacher.get('name')}, 研究室：{teacher.get('lab')}<br>"
                found = True
        
        if not found:
            Result += "抱歉，查無此關鍵字之老師資料。"


        return Result + "<br><a href='/read3'>重新查詢</a> | <a href='/'>回首頁</a>"
    else:
        html="""
        <h2>老師查詢</h2>
        <form action="/read3" method="POST">
            請輸入老師姓名關鍵字
            <input type="text" name="keyword">
            <button type="submit">查詢</button>
        </from>
        <br><a href="/">回首頁</a>
        """
        # GET 請求時，顯示輸入表單
        return html


@app.route("/spider")
def spider():
    Result=""
    url = "https://www1.pu.edu.tw/~tcyang/course.html"
    Data = requests.get(url)
    Data.encoding = "utf-8"
    #print(Data.text)
    sp = BeautifulSoup(Data.text, "html.parser")
    result=sp.select(".team-box a")
    for i in result:
        Result+=str(i.text)+str(i.get("href"))+"<br>"
    return Result

@app.route("/movie1", methods=["GET", "POST"])
def movie1():
    if request.method == "POST":
        # 取得使用者輸入的關鍵字
        keyword = request.values.get("keyword")
        
        url = "https://www.atmovies.com.tw/movie/next/"
        Data = requests.get(url)
        Data.encoding = "utf-8"
        sp = BeautifulSoup(Data.text, "html.parser")
        result = sp.select(".filmListAllX li")
        
        R = f"<h2>您搜尋的關鍵字是：{keyword}</h2>"
        found = False
        
        for item in result:
            # 取得電影名稱
            movie_name = item.find("img").get("alt")
            
            # 檢查關鍵字是否在片名中 (不分大小寫可用 .lower())
            if keyword in movie_name:
                found = True
                introduce = "https://www.atmovies.com.tw" + item.find("a").get("href")
                post = "https://www.atmovies.com.tw" + item.find("img").get("src")
                
                R += f"<a href='{introduce}' target='_blank'>{movie_name}</a><br>"
                R += f"<img src='{post}' style='width:200px;'><br><br>"
        
        if not found:
            R += "<p>抱歉，查無包含此關鍵字的即將上映電影。</p>"
            
        return R + "<br><a href='/movie1'>重新查詢</a> | <a href='/'>回首頁</a>"
    
    else:
        # GET 請求：顯示查詢介面
        html = """
        <h2>即將上映電影查詢</h2>
        <form action="/movie1" method="POST">
            請輸入電影片名關鍵字：
            <input type="text" name="keyword" required>
            <button type="submit">搜尋</button>
        </form>
        <br><a href="/">回首頁</a>
        """
        return html


if __name__ == "__main__":
    app.run(debug=True)