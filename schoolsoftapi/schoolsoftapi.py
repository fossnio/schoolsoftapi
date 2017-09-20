'''介接全誼校務系統'''

import os
import re
import io
import subprocess
import tempfile
import time
import csv
from datetime import datetime

import requests
import xlrd


class SchoolSoftAPI:
    '''透過 WEBUI 介接全誼校務系統'''

    def __init__(self, username, password, semester, baseurl='https://eschool.tp.edu.tw'):
        '''初始化'''

        self.username = username
        self.password = password
        self.semester = semester
        self.baseurl = baseurl
        self.session = requests.Session()
        requests.packages.urllib3.disable_warnings()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0'})
        self.response = None
        self.students = []
        self.teachers = []

    def login(self, retry=True, wait=300):
        '''登入校務系統'''

        self.session.get('{0}/index.jsp'.format(self.baseurl))
        self.session.post('{0}/login.jsp'.format(self.baseurl), data={'method': 'getLogin', 'auth_type': '', 'auth_role': '', 'showTitle': '0'})

        if self._login_with_captcha():
            return True
        else:
            while True:
                if retry is not True:
                    if retry > 0:
                        retry -= 1
                    else:
                        return False
                time.sleep(wait)
                if self._login_with_captcha():
                    return True

    def _login_with_captcha(self):
        '''辨識 captcha 後送出認證並回傳登入結果'''

        self.response = self.session.get('{0}/web-sso/rest/Redirect/login/page/normal?returnUrl={0}/WebAuth.do'.format(self.baseurl))

        # 取得 post 網址
        post_url = re.findall(r' action="(.+?)"', self.response.text)[0]

        # 圖形認證碼下載並丟給 tesseract 直到辨認出是 5 個數字
        while True:

            self.response = self.session.get('{0}/RandomNum?t={1}'.format(self.baseurl, int(datetime.now().timestamp() * 1000)), stream=True)

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
        self.response = self.session.post('{0}{1}'.format(self.baseurl, post_url), data={'username': self.username, 'password': self.password, 'random_num': captcha_number})

        if '登入失敗' in self.response.text:
            return False
        else:
            self._grant_admin_permission()
            return True

    def _grant_admin_permission(self):
        '''切換成資訊人員權限'''
        self.response = self.session.get('{0}/Module_List.do'.format(self.baseurl))
        grant_admin_link = re.search(
            r'''onclick="location.href='/(Change_Auth.do\?pos_id=\w+&pid=\d+)'"> (?:資訊組長|系統管理師)</font>''',
            self.response.text
        ).group(1)
        self.session.get('{0}/{1}'.format(self.baseurl, grant_admin_link))

    def _get_post_data_file(self, url, data):
        '''校務系統通過 post 匯出檔案的一般化邏輯'''
        self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        self.response = self.session.post(url, data, stream=True)
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        tmp_file.write(self.response.raw.read())
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

    def _get_teachers_job_info_csv(self):
        '''取得教師職務，並轉化成 key 為身份證字號的資料結構以便於後續合併'''
        teachers_job_info = {}
        self.session.get(
            '{0}/jsp/people/teasrv_data.jsp?seyear={1}&sesem={2}'.format(self.baseurl, self.semester[:-1], self.semester[-1]),
            verify=False
        )
        self.response = self.session.get(
            '{0}/jsp/people/teasrv_destiny.jsp?filename=data.csv'.format(self.baseurl),
            stream=True,
            verify=False
        )
        for row in csv.reader(io.StringIO(self.response.raw.read().decode('utf-8'))):
            # 共五欄且第一欄為數字才處理
            if len(row) == 5 and row[0].isdigit():
                teachers_job_info[row[3]] = {'job_title': row[1], 'class': row[4]}
        return teachers_job_info

    def _to_csv(self, headers, order, entities):
        '''將傳入的資料結構 entities 轉成 csv 格式'''
        csv_content = io.StringIO()
        csv_writer = csv.writer(csv_content)
        csv_writer.writerow(headers)
        for entity in entities:
            row = [entity[i].strftime('%Y%m%d') if isinstance(entity[i], datetime) else entity[i] for i in order]
            csv_writer.writerow(row)
        csv_content.seek(0)
        return csv_content.read()

    def dump_students(self, output_format='raw'):
        '''將下載下來的學生 xls 取出需要的欄位轉成資料結構'''
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
                    'grade': int(sheet.cell(i, 2).value),
                    # 班級
                    'class': sheet.cell(i, 3).value,
                    # 生日
                    'birthday': datetime.strptime(sheet.cell(i, 4).value, '%Y%m%d'),
                    # 座號
                    'seat_number': int(sheet.cell(i, 5).value),
                    # 身份證字號
                    'identity': sheet.cell(i, 6).value
                } for i in range(1, sheet.nrows)
            ]
        os.unlink(xls_file)
        if output_format == 'csv':
            return self._to_csv(
                ['學號', '姓名', '年級', '班級', '生日', '座號', '身份證字號'],
                ['student_id', 'name', 'grade', 'class', 'birthday', 'seat_number', 'identity'],
                self.students
            )
        else:
            return self.students

    def dump_teachers(self, output_format='raw'):
        '''將下載下來的教師 xls 取出需要的欄位並對照職稱 csv 內容轉成資料結構'''
        xls_file = self._get_teachers_xls_file()
        job_info = self._get_teachers_job_info_csv()
        with xlrd.open_workbook(xls_file) as f:
            sheet = f.sheet_by_index(0)
            for i in range(2, sheet.nrows):
                # 將生日從民國轉成西元
                birthday = '{0}{1}'.format(int(sheet.cell(i, 3).value[:-4]) + 1911, sheet.cell(i, 3).value[-4:])
                teacher = {
                    # 身份證字號
                    'identity': sheet.cell(i, 0).value,
                    # 教師姓名
                    'name': sheet.cell(i, 1).value,
                    # 性別
                    'gender': sheet.cell(i, 2).value,
                    # 生日
                    'birthday': datetime.strptime(birthday, '%Y%m%d'),
                    # 電子郵件
                    'email': sheet.cell(i, 6).value,
                    # 職稱
                    'job_title': '',
                    # 帶的班級
                    'class': ''
                }
                if teacher['identity'] in job_info:
                    teacher['job_title'] = job_info[teacher['identity']]['job_title']
                    teacher['class'] = job_info[teacher['identity']]['class']
                self.teachers.append(teacher)
        os.unlink(xls_file)
        if output_format == 'csv':
            return self._to_csv(
                ['身份證字號', '姓名', '性別', '生日', '電子郵件', '職稱', '班級'],
                ['identity', 'name', 'gender', 'birthday', 'email', 'job_title', 'class'],
                self.teachers
            )
        else:
            return self.teachers

    def delete_teacher(self, identity, name, gender, birthday):
        '''刪除教師'''

        # 讓校務系統記住我們要存取哪個模組以免報錯
        self.session.get('{0}/Module_Change.do?pid=0070&module=people&path=&moduleName=人事資料管理'.format(self.baseurl))

        # 取得校務系統紀錄教師帳號的 key teaid
        self.response = self.session.get('{0}/jsp/people/teabasicdata.jsp'.format(self.baseurl))
        re_result = re.search(r'''<font size="2"><a name='tea(\S+)'></a>{0}</font>'''.format(name), self.response.text)
        schoolsoft_teaid= re_result.group(1)

        # 轉換生日成所需的格式
        schoolsoft_birthday1 = '{0}/{1}'.format(int(birthday.strftime('%Y')) - 1911, birthday.strftime('%m/%d'))
        schoolsoft_birthday2 = birthday.strftime('%Y%m%d')

        self.response = self.session.post(
            '{0}/jsp/people/teabasicdata_s.jsp'.format(self.baseurl),
            data={
                'x': 11,
                'y': 10,
                'teaname': '測試二',
                'teasex': gender, # 1 是男生， 0 是女生
                'teasexx': gender,
                'teaBirthday1': schoolsoft_birthday1,
                'teaBirthday2': schoolsoft_birthday2,
                'work': 6, # 人事不管校務系統，所以統一設定為專任
                'atschool': 0, # 0 代表離校
                'teacourse': '',
                'teawordno': '',
                'teaWordDate11': '',
                'teaWordDate1': '',
                'teacourse2': '',
                'teawordno2': '',
                'teaWordDate22': '',
                'teaWordDate2': '',
                'teacourse3': '',
                'teawordno3': '',
                'teaWordDate33': '',
                'teaWordDate3': '',
                'teacourse4': '',
                'teawordno4': '',
                'teaWordDate44': '',
                'teaWordDate4': '',
                'teacourse5': '',
                'teawordno5': '',
                'teaWordDate55': '',
                'teaWordDate5': '',
                'teacourse6': '',
                'teawordno6': '',
                'teaWordDate66': '',
                'teaWordDate6': '',
                'teacourse7': '',
                'teawordno7': '',
                'teaWordDate77': '',
                'teaWordDate7': '',
                'teacourse8': '',
                'teawordno8': '',
                'teaWordDate88': '',
                'teaWordDate8': '',
                'teacourse9': '',
                'teawordno9': '',
                'teaWordDate99': '',
                'teaWordDate9': '',
                'teacourse10': '',
                'teawordno10': '',
                'teaWordDate1010': '',
                'teaWordDate10': '',
                'tai_date2': '',
                'tai_date': '',
                'tai_word': '',
                'hak_date2': '',
                'hak_date': '',
                'hak_word': '',
                'abo_date2': '',
                'abo_date': '',
                'abo_word': '',
                'teamerrage': 0,
                'hanndy': 0,
                'place': '',
                'nature': '',
                'teamail': '',
                'schphone': '',
                'schextn': '',
                'schfax': '',
                'teaphone': '',
                'teamobil': '',
                'hpostal': '',
                'hpa': '',
                'hpb': '',
                'hpc': '',
                'hpd': '',
                'hpe': '',
                'cpostal': '',
                'cpa': '',
                'cpb': '',
                'cpc': '',
                'cpd': '',
                'cpe': '',
                'teaaddress': '',
                'teaTeachDate1': '',
                'teaTeachDate2': '',
                'teaArriveDate1': '',
                'teaArriveDate2': '',
                'reglib': 0,
                'birthplace': '',
                'teasalary': '',
                'highedu': '',
                'teagradu': '',
                'teadepart': '',
                'teamemo': '',
                'action': 'change',
                'teaId': schoolsoft_teaid,
                'teaidno': identity,
                'seniority': '',
                'chyear': '',
                'real_seniority': '',
                'my_check': 0,
                'schoolNo': '',
            },
            files={'teapic': ('', '')}
        )
        
        return True if identity in self.response.text else False

    def add_teacher(self, identity, name, gender, birthday):
        '''新增教師'''

        # 讓校務系統記住我們要存取哪個模組以免報錯
        self.session.get('{0}/Module_Change.do?pid=0070&module=people&path=&moduleName=人事資料管理'.format(self.baseurl))

        # 轉換生日成所需的格式
        schoolsoft_birthday1 = '{0}/{1}'.format(int(birthday.strftime('%Y')) - 1911, birthday.strftime('%m/%d'))
        schoolsoft_birthday2 = birthday.strftime('%Y%m%d')

        self.response = self.session.post(
            '{0}/jsp/people/teabasicdata_s.jsp'.format(self.baseurl),
            data={
                'x': 11,
                'y': 10,
                'people_type': '',
                'teaidno': identity,
                'teaname': name,
                'teasex': gender, # 1 是男生， 0 是女生
                'teaBirthday1': schoolsoft_birthday1,
                'teaBirthday2': schoolsoft_birthday2,
                'work': 6, # 人事不管校務系統，所以統一設定為專任
                'atschool': 1, # 1 代表在校
                'teacourse': '',
                'teawordno': '',
                'teaWordDate11': '',
                'teaWordDate1': '',
                'teacourse2': '',
                'teawordno2': '',
                'teaWordDate22': '',
                'teaWordDate2': '',
                'teacourse3': '',
                'teawordno3': '',
                'teaWordDate33': '',
                'teaWordDate3': '',
                'teacourse4': '',
                'teawordno4': '',
                'teaWordDate44': '',
                'teaWordDate4': '',
                'teacourse5': '',
                'teawordno5': '',
                'teaWordDate55': '',
                'teaWordDate5': '',
                'teacourse6': '',
                'teawordno6': '',
                'teaWordDate66': '',
                'teaWordDate6': '',
                'teacourse7': '',
                'teawordno7': '',
                'teaWordDate77': '',
                'teaWordDate7': '',
                'teacourse8': '',
                'teawordno8': '',
                'teaWordDate88': '',
                'teaWordDate8': '',
                'teacourse9': '',
                'teawordno9': '',
                'teaWordDate99': '',
                'teaWordDate9': '',
                'teacourse10': '',
                'teawordno10': '',
                'teaWordDate1010': '',
                'teaWordDate10': '',
                'tai_date2': '',
                'tai_date': '',
                'tai_word': '',
                'hak_date2': '',
                'hak_date': '',
                'hak_word': '',
                'abo_date2': '',
                'abo_date': '',
                'abo_word': '',
                'teamerrage': 0,
                'hanndy': 0,
                'place': '',
                'nature': '',
                'teamail': '',
                'schphone': '',
                'schextn': '',
                'schfax': '',
                'teaphone': '',
                'teamobil': '',
                'hpostal': '',
                'hpa': '',
                'hpb': '',
                'hpc': '',
                'hpd': '',
                'hpe': '',
                'cpostal': '',
                'cpa': '',
                'cpb': '',
                'cpc': '',
                'cpd': '',
                'cpe': '',
                'teaaddress': '',
                'teaTeachDate1': '',
                'teaTeachDate2': '',
                'teaArriveDate1': '',
                'teaArriveDate2': '',
                'reglib': 0,
                'birthplace': '',
                'teasalary': '',
                'highedu': '',
                'teagradu': '',
                'teadepart': '',
                'teamemo': '',
                'action': 'add',
                'seniority': '',
                'chyear': '',
                'real_seniority': '',
                'schoolNo': '',
            },
            files={'teapic': ('', '')}
        )

        return True if identity in self.response.text else False
