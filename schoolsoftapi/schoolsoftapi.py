'''介接全誼笑務系統'''

import re
import io
import subprocess
import tempfile
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

                # 抓回來的圖直接丟入 tesseract-ocr，並將結果從 stdout 取得
                captcha_number = subprocess.Popen(
                    ['tesseract', 'stdin', 'stdout'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE
                ).communicate(self.response.raw.read())[0].decode('utf-8').strip()

                # 必須是 5 個數字，否則重跑
                if captcha_number and captcha_number.isdigit() and len(captcha_number) == 5:
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

    def _get_post_data(self, url, data):
        '''校務系統通過 post 匯出檔案的一般化邏輯'''
        self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        response = self.session.post(url, data, stream=True, verify=False)
        tmp_file = tempfile.TemporaryFile()
        tmp_file.write(response.raw.read())
        tmp_file.seek(0)
        return tmp_file

    def _get_students_xml(self):
        '''取得所有學生資料，原始格式為 xml'''
        url = '{0}/jsp/std_search/search_r.jsp'.format(self.baseurl)
        data = 'selsyse={0}&syse={0}&VIEW=student.stdno&VIEW=student.name&VIEW=student.year%7C%7Cstudent.classno+as+classid&sex=1&blood=A&VIEW=student.birthday&view_birthday=1&christic=01&VIEW=student.no&VIEW=student.idno&flife=0&mlife=0&slife=0&submit_type=xml&x=31&y=11&sql='.format(self.semester)
        return self._get_post_data(url, data)

    def _get_teachers_xml(self):
        '''取得老師資訊，格式為 xml'''
        url = '{0}/jsp/tea_search/search_mix_s.jsp'.format(self.baseurl)
        data = 'x=16&y=11&ck1=1&teaname=&ck12=1&teaidno=&birthplace=&teaphone=&regstring=&ck14=1&teamail=&teaaddress=&teamobil=&ck5=1&ck6=1&birthyear=&birthmonth=&birthday=&birthyear1=&birthmonth1=&birthday1=&teachyear=&teachmonth=&teachday=&teachyear1=&teachmonth1=&teachday1=&reglib=0&work=0&highedu=0&teagradu='
        return self._get_post_data(url, data)

    def _get_teacher_duties(self):
        '''取得教師職務'''
        self.session.get(
            '{0}/jsp/people/teasrv_data.jsp?seyear={1}&sesem={2}'.format(self.baseurl, self.semester[:-1], self.semester[-1]),
            verify=False
        )
        response = self.session.get(
            '{0}/jsp/people/teasrv_destiny.jsp?filename=data.csv'.format(self.baseurl),
            stream=True,
            verify=False
        )
        return io.BytesIO(response.raw.read())

