from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import os
import json  # json モジュールのインポートが必要です

# Google Sheets API 関連のインポート
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'  # フォームのセキュリティに必要

# Google Sheets API のスコープと認証情報
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Renderの環境変数からcredentials.jsonの内容を取得
google_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
if google_creds:
    credentials_info = json.loads(google_creds)
    credentials = service_account.Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
else:
    raise ValueError("Google credentials not found")

# Google Sheets API サービスの初期化
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# スプレッドシートのID（あなたのスプレッドシートのIDに置き換えてください）
CAGE_DATA_SPREADSHEET_ID = '1nt1MPFZEk1I9stwY8JOvsjJhQHlQAaOE4BH8G0SEgkM'  # cage_data
MOUSE_STRAINS_SPREADSHEET_ID = '190hLGCInKtdL0Jt50opJMRwb_bpKucf8M4drS7JvnyQ'  # mouse_strains

# ケージ情報を保持する辞書
# キーは (rack, row, col) のタプル
cage_dict = {}  # ケージ情報を格納

# 系統リストとユーザーリスト
strain_list = []
user_list = []

# ケージデータをスプレッドシートから読み込む関数
def load_cage_data():
    result = sheet.values().get(
        spreadsheetId=CAGE_DATA_SPREADSHEET_ID,
        range='Sheet1!A2:K'  # データの範囲（必要に応じて変更）
    ).execute()
    values = result.get('values', [])
    cages = []
    for row in values:
        cage = {
            'rack': row[0],
            'row': int(row[1]),
            'col': int(row[2]),
            'cage_id': row[3],
            'strain': row[4],
            'count': int(row[5]),
            'gender': row[6],
            'usage': row[7],
            'user': row[8],
            'dob': row[9] if len(row) > 9 else '',
            'note': row[10] if len(row) > 10 else ''
        }
        cages.append(cage)
    return cages

# ケージデータをスプレッドシートに書き込む関数
def save_cage_data(cages):
    values = []
    for cage in cages:
        values.append([
            cage['rack'],
            cage['row'],
            cage['col'],
            cage['cage_id'],
            cage['strain'],
            str(cage['count']),  # 数値を文字列に変換
            cage['gender'],
            cage['usage'],
            cage['user'],
            cage.get('dob', ''),
            cage.get('note', '')
        ])
    body = {
        'values': values
    }
    sheet.values().update(
        spreadsheetId=CAGE_DATA_SPREADSHEET_ID,
        range='Sheet1!A2',
        valueInputOption='RAW',
        body=body
    ).execute()

# 系統リストとユーザーリストをスプレッドシートから読み込む関数
def load_strains_and_users():
    result = sheet.values().get(
        spreadsheetId=MOUSE_STRAINS_SPREADSHEET_ID,
        range='Sheet1!A2:B'  # データの範囲（必要に応じて変更）
    ).execute()
    values = result.get('values', [])
    strains = []
    users = []
    for row in values:
        if row[0] not in strains:
            strains.append(row[0])
        if len(row) > 1 and row[1] not in users:
            users.append(row[1])
    return strains, users

# アプリケーション起動時にデータをロード
def load_data():
    cages = load_cage_data()
    for cage in cages:
        key = (cage['rack'], cage['row'], cage['col'])
        cage_dict[key] = cage
    global strain_list, user_list
    strain_list, user_list = load_strains_and_users()

load_data()

# データ表示用のルート
@app.route('/')
def index():
    # 現在のラックを取得（デフォルトはラックA）
    current_rack = request.args.get('rack', 'A')
    # 選択されたユーザーのフィルター
    selected_user = request.args.get('user', None)

    # ケージ情報をフィルタリング
    rack_cages = []
    for key, cage in cage_dict.items():
        if cage['rack'] == current_rack:
            if not selected_user or cage['user'] == selected_user:
                rack_cages.append(cage)

    # ラック内のケージ数とマウス数を計算
    filled_cages = len(rack_cages)
    total_mice = sum(cage['count'] for cage in rack_cages)

    # 全体のケージ数とマウス数を計算
    total_filled_cages = len(cage_dict)
    total_mice_all = sum(cage['count'] for cage in cage_dict.values())

    return render_template('index.html',
                           rack_names=['A', 'B', 'C', 'D'],
                           current_rack=current_rack,
                           cages=rack_cages,
                           filled_cages=filled_cages,
                           total_mice=total_mice,
                           total_filled_cages=total_filled_cages,
                           total_mice_all=total_mice_all,
                           user_list=user_list,
                           selected_user=selected_user)

# ケージの詳細表示と編集用のルート
@app.route('/cage/<rack>/<int:row>/<int:col>', methods=['GET', 'POST'])
def cage_detail(rack, row, col):
    key = (rack, row, col)
    cage = cage_dict.get(key, {
        'rack': rack,
        'row': row,
        'col': col,
        'cage_id': '',
        'strain': strain_list[0] if strain_list else '',
        'count': 0,
        'gender': 'Male',
        'usage': 'Maintain',
        'user': user_list[0] if user_list else '',
        'dob': '',
        'note': ''
    })

    if request.method == 'POST':
        cage['cage_id'] = request.form['cage_id']
        cage['user'] = request.form['user']
        cage['strain'] = request.form['strain']
        cage['count'] = request.form['count']
        cage['gender'] = request.form['gender']
        cage['usage'] = request.form['usage']
        cage['dob'] = request.form.get('dob', '')
        cage['note'] = request.form.get('note', '')

        # バリデーション
        if not cage['cage_id'] or not cage['user'] or not cage['strain'] or not cage['count'] or not cage['gender'] or not cage['usage']:
            flash("Please fill in all required fields.")
            return redirect(request.url)
        if not str(cage['count']).isdigit():
            flash("Number of Mice must be a positive integer.")
            return redirect(request.url)
        if cage['usage'] == "New born" and not cage['dob']:
            flash("Please provide DOB for New born mice.")
            return redirect(request.url)

        cage['count'] = int(cage['count'])  # 型変換

        cage_dict[key] = cage
        save_cage_data(list(cage_dict.values()))

        return redirect(url_for('index', rack=rack))

    return render_template('cage_detail.html',
                           rack=rack,
                           row=row,
                           col=col,
                           cage_info=cage,
                           strain_list=strain_list,
                           user_list=user_list)

# ケージを空にするためのルート
@app.route('/empty_cage/<rack>/<int:row>/<int:col>', methods=['POST'])
def empty_cage(rack, row, col):
    key = (rack, row, col)
    if key in cage_dict:
        del cage_dict[key]
        save_cage_data(list(cage_dict.values()))
    return redirect(url_for('index', rack=rack))

# ユーザーサマリーの表示
@app.route('/summary', methods=['GET'])
def summary():
    user = request.args.get('user', '')
    if not user:
        flash("Please select a user.")
        return redirect(url_for('index'))

    user_cages = [cage for cage in cage_dict.values() if cage['user'] == user]
    total_cages = len(user_cages)
    total_mice = sum(cage['count'] for cage in user_cages)
    strains = {cage['strain'] for cage in user_cages}

    return render_template('summary.html',
                           user=user,
                           total_cages=total_cages,
                           total_mice=total_mice,
                           strains=strains)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
