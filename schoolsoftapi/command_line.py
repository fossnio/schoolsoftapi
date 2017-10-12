# This program is released under license GPL v3,
# see LICENSE.rst for more details.
# Copyright 2017 FOSS Ninja
'''命令列工具，方便使用者直接調用而無須涉入 API 的使用細節'''

import logging
import argparse
from pprint import pprint

from schoolsoftapi import SchoolSoftAPI


def main():
    parser = argparse.ArgumentParser(description='SchoolSoft 非官方命令列工具')
    parser.add_argument('-u', '--user', required=True, help='校務系統資訊人員帳號')
    parser.add_argument('-p', '--password', required=True, help='校務系統資訊人員密碼')
    parser.add_argument('-x', '--semester', required=True, type=int, help='學期，比如 106 上學期為 1061')
    parser.add_argument('-r', '--retry', type=int, default=3, help='重試登入的次數上限')
    parser.add_argument('-w', '--wait', type=int, default=1, help='登入失敗重試前等待秒數')
    parser.add_argument('-v', '--verbose', action='store_true', help='顯示詳細資訊')
    parser.add_argument('-d', '--debug', action='store_true', help='開啟除錯模式')
    parser.add_argument('-s', '--students', action='store_true', help='傾印學生資料')
    parser.add_argument('-t', '--teachers', action='store_true', help='傾印教師資料')
    args = parser.parse_args()
    
    logger = logging.getLogger('schoolsoftapi')

    if args.debug:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(message)s', '%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    ssa = SchoolSoftAPI(args.user, args.password, args.semester)
    ssa.login(retry=args.retry, wait=args.wait)
    
    if args.teachers:
        pprint(ssa.dump_teachers())
    
    if args.students:
        pprint(ssa.dump_students())
