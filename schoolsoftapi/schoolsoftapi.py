'''介接全誼笑務系統'''

import re
import shutil
import subprocess
import time
from datetime import datetime

import requests

class SchoolSoftAPI:
    '''透過 WEBUI 介接全誼校務系統'''

    def __init__(self, username, password, semester, baseurl='https://eschool.tp.edu.tw'):
        '''初始化'''

        self.username = username
        self.password = password
        self.semester = semester
        self.baseurl = baseurl
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': '"Mozilla/5.0 (X11; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0"'})
        self.response = None

    def login(self):
        '''登入校務系統'''

        self.session.get('{0}/index.jsp'.format(self.baseurl), verify=False)
        self.session.post('{0}/login.jsp'.format(self.baseurl), data={'method': 'getLogin', 'auth_type': '', 'auth_role': '', 'showTitle': '0'}, verify=False)

        # 重複跑直到 capcha 成功辨識出是 5 個數字（對錯不管）
        while True:
            self.response = self.session.get('{0}/web-sso/rest/Redirect/login/page/normal?returnUrl={0}/WebAuth.do'.format(self.baseurl), verify=False)

            # 取得 post 網址
            post_url = re.findall(r' action="(.+?)"', self.response.text)[0]

            # 圖形認證碼下載並丟給 tesseract 直到辨認出是 5 個數字
            while True:

                self.response = self.session.get('{0}/RandomNum?t={1}'.format(self.baseurl, int(datetime.now().timestamp() * 1000)), stream=True, verify=False)

                with open('/tmp/random_number.jpeg', 'wb') as f:
                    shutil.copyfileobj(self.response.raw, f)

                # 丟入 tesseract-ocr
                captcha_number = subprocess.getoutput('tesseract /tmp/random_number.jpeg stdout').strip()

                # 必須是 5 個數字，否則重跑
                if captcha_number.isdigit() and len(captcha_number) == 5:
                    break
                else:
                    time.sleep(5)

            # 認證
            self.response = self.session.post('{0}{1}'.format(self.baseurl, post_url), data={'username': self.username, 'password': self.password, 'random_num': captcha_number}, verify=False)

            if '登入失敗' in self.response.text:
                # 等 5 分鐘，避開失敗 5 次被停權 15 分鐘的限制
                time.sleep(300)
            else:
                break
