# 網路爬蟲蒐集AI圖片訓練素材
*——僅供學術研究用途，練習如何爬蟲，取得之素材勿訴諸商業用途*


![流程概念圖](https://219.69.20.132/static/crawler.png)
- 使用scrapy模組進行網路爬蟲，透過python腳本自動化下載圖片及擷取資訊
- 了解目標網站運作行為及底層結構，以國內某遊戲自製網站為例，內存動漫風格人物角色之創作素材
    - 全部約3800多個角色，角色列表共有400多頁，每頁顯示9個人物
    - 進入角色頁後，每位人物可能有數張不同表情動作的圖片(少則1張，多則20-30張)，每頁均顯示4張
    - 除了擷取角色的圖片素材，也需擷取針對角色的描述及標籤
- 透過xpath定位節點，找到目標html網頁元素進行操控、讀取指定數值
- 注重thread-safe，不同執行緒會寫入同一份角色說明文件，透過lock保障檔案的正確性
- 設定每個請求的間隔一定秒數(DOWNLOAD_DELAY參數)，防止網站突面臨大量請求而潰堤
- 可設定每次程式執行的角色擷取上限(例如只取100個角色)；如程式中斷具銜接機制，補齊未執行完成之處，確保資料完整性
---

1. 模擬初始登入行為->after_login() 
```
需事先於網站中註冊會員，接著修改LOGIN_ID、LOGIN_PASSWORD參數代入個人帳密資訊，
爬蟲程式將模擬登入行為，並透過取得cookie記下帳戶session狀態，以利查看角色列表（僅會員狀態下能瀏覽）
```

2. parse_character_list(): 從角色列表取得進入角色頁之連結，並yield衍生新的爬蟲請求
```
為每個角色創建資料夾及生成描述文件info.json，建立lock供新執行緒協調寫入
```

3. parse_pose_list(): 進入角色頁後，擷取角色描述內容，並下載每張表情動作圖片
```
取得角色資訊說明，將人物標籤及表情動作加入info.json，下載圖檔
```

---
## 環境安裝及程式執行

主要程式位置在./crawler_project/spiders底下的collect_spider.py，其餘為scrapy startproject時自動產生之檔案。

請確保*scrapy*及*requests*模組已安裝，接著可透過下列指令來啟動scarpy：
```
cd ./crawler_project
scrapy crawl collect_spider
```
> 上述collect_spider名稱與CollectCharacterSpider類別中的name值一致


爬蟲蒐集到的資料將存於./dataset/中，如欲變更可修改SAVE_DIR_ROOT變數。
