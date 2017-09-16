'''介接全誼校務系統'''

import os
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
        self.students = None

    def login(self, retry=True, wait=300):
        '''登入校務系統'''

        self.session.get('{0}/index.jsp'.format(self.baseurl), verify=False)
        self.session.post('{0}/login.jsp'.format(self.baseurl), data={'method': 'getLogin', 'auth_type': '', 'auth_role': '', 'showTitle': '0'}, verify=False)

        # 重複跑直到 capcha 成功辨識出是 5 個數字（對錯不管）
        while retry:
            self.response = self.session.get('{0}/web-sso/rest/Redirect/login/page/normal?returnUrl={0}/WebAuth.do'.format(self.baseurl), verify=False)

            # 取得 post 網址
            post_url = re.findall(r' action="(.+?)"', self.response.text)[0]

            # 圖形認證碼下載並丟給 tesseract 直到辨認出是 5 個數字
            while True:

                self.response = self.session.get('{0}/RandomNum?t={1}'.format(self.baseurl, int(datetime.now().timestamp() * 1000)), stream=True, verify=False)

                # 抓回來的圖直接丟入 tesseract-ocr，並將結果從 stdout 取得(指定只辨識數字)
                captcha_number = subprocess.Popen(
                    ['tesseract', 'stdin', 'stdout', 'digits'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE
                ).communicate(self.response.raw.read())[0].decode('utf-8').strip()

                # 辨識出的數字長度必須是 5 ，否則重跑
                if captcha_number and len(captcha_number) == 5:
                    break
                else:
                    time.sleep(1)

            # 認證
            self.response = self.session.post('{0}{1}'.format(self.baseurl, post_url), data={'username': self.username, 'password': self.password, 'random_num': captcha_number}, verify=False)

            if '登入失敗' in self.response.text:
                # 等待，避開失敗 5 次被停權 15 分鐘的限制
                time.sleep(wait)
            else:
                return True

            if retry is not True:
                retry -= 1
                if retry == 0:
                    return False

    def _get_post_data_file(self, url, data):
        '''校務系統通過 post 匯出檔案的一般化邏輯'''
        self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        response = self.session.post(url, data, stream=True, verify=False)
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        tmp_file.write(response.raw.read())
        tmp_file.close()
        return tmp_file.name

    def _get_students_xls_file(self):
        '''取得所有學生資料，原始格式為 xls'''
        url = '{0}/jsp/std_search/search_r.jsp'.format(self.baseurl)
        data = 'selsyse={0}&syse={0}&VIEW=student.stdno&VIEW=student.name&VIEW=student.year%7C%7Cstudent.classno+as+classid&sex=1&blood=A&VIEW=student.birthday&view_birthday=1&christic=01&VIEW=student.no&VIEW=student.idno&flife=0&mlife=0&slife=0&submit_type=excel&x=31&y=11&sql='.format(self.semester)
        return self._get_post_data_file(url, data)

    def _get_teachers_xls_file(self):
        '''取得所有老師資料，原始格式為 xls'''
        url = '{0}/jsp/people/teaDataCsv.jsp'.format(self.baseurl)
        data = 'username=&password=&chkall=on&colnames=idno&colnames=teaname&colnames=teasex&colnames=birthday&colnames=birthplace&colnames=teaphone&colnames=teamail&colnames=teamerrage&colnames=hanndy&colnames=teachdate&colnames=arrivedate&colnames=reglib&colnames=atschool&colnames=worklib&colnames=highedu&colnames=teagradu&colnames=teadepart&colnames=teacourse&colnames=teawordno&colnames=teamemo&colnames=teamobil&colnames=teasalary&colnames=schphone&colnames=schextn&colnames=place&colnames=nature&colnames=hpa&colnames=hpb&colnames=hpc&colnames=hpd&colnames=hpe&colnames=cpa&colnames=cpb&colnames=cpc&colnames=cpd&colnames=cpe&colnames=hpostal&colnames=cpostal&colnames=teaworddate&colnames=teaname_e&colnames=christic&datatrans='
        return self._get_post_data_file(url, data)

    def _get_teacher_duty_csv(self):
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
        return io.StringIO(response.raw.read().decode('utf-8'))

    def _jsonify_students_xls_file(self):
        '''將下載下來的學生 xls 取出需要的欄位轉成 json'''
        import xlrd

        xls_file = self._get_students_xls_file()
        with xlrd.open_workbook(xls_file) as f:
            sheet = f.sheet_by_index(0)
            self.students = [
                {
                    # 學號
                    'student_id': sheet.cell(i, 0).value,
                    # 學生姓名
                    'name': sheet.cell(i, 1).value,
                    # 年級
                    'grade': sheet.cell(i, 2).value,
                    # 班級
                    'class': sheet.cell(i, 3).value,
                    # 生日
                    'birthday': sheet.cell(i, 4).value,
                    # 座號
                    'seat_number': sheet.cell(i, 5).value,
                    # 身份證字號
                    'identify': sheet.cell(i, 6).value
                } for i in range(1, sheet.nrows)
            ]
        os.unlink(xls_file)
        return self.students
