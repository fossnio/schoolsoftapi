安裝
====

外部套件
------------

本專案依靠 tesseract 處理圖形 captcha，因此需要安裝相關套件：

.. code:: bash
    
    sudo apt install tesseract-ocr -y

Python 套件
-----------

本專案只在 Python 3.5+ 版本上測試過，建議使用 Python 3.5+ 以上版本運行。安裝建議使用 venv 標準函式庫建立虛擬環境安裝套件，在 Debian Stretch 中必須執行：

.. code:: bash
    
    sudo apt install python3-venv -y

才能使用 venv 標準函式庫建立虛擬環境：

.. code:: bash
    
    mkdir -p ~/venv
    python3 -m venv ~/venv/schoolsoftapi
    source ~/venv/schoolsoftapi/bin/activate
    pip install schoolsoftapi

使用 API
========

.. code:: python
    
    from schoolsoftapi import SchoolSoftAPI
    # 傳入的 1061 代表 106 學年度第 1 學期
    api = SchoolSoftAPI('校務系統帳號', '校務系統密碼', '1061')
    # 若 captcha 辨識失敗導致無法登入，等待 5 秒重試
    api.login(wait=5)
    # 傾印學生資料
    api.dump_students()
    # 傾印教師資料含職務
    api.dump_teachers()
    # 新增教師帳號
    api.add_teacher('K123456789', '王大明', '男', datetime.now())
    # 重設教師密碼
    api.reset_teacher_password('K123456789', '王大明')
    # 刪除教師教師帳號
    api.delete_teacher('K123456789', '王大明', '男', datetime.now())

