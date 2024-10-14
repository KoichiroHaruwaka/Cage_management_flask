from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import os
import json
import re  # 正規表現モジュールを追加

# Google Sheets API 関連のインポート
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Flask-WTF と CSRF 対策のインポート
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, IntegerField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'  # セキュリティのために安全なキーを設定してください

# CSRF対策の初期化
csrf = CSRFProtect(app)

# Google Sheets API のスコープと認証情報
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 環境変数からcredentials.jsonの内容を取得
google_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
if google_creds:
    credentials_info = json.loads(google_creds)
    credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
else:
    raise ValueError("Google credentials not found")

# Google Sheets API サービスの初期化
service = build('sheets', 'v4', credentials=credentials)
sheet = service.spreadsheets()

# スプレッドシートのID
CAGE_DATA_SPREADSHEET_ID = '1nt1MPFZEk1I9stwY8JOvsjJhQHlQAaOE4BH8G0SEgkM'  # cage_data
MOUSE_STRAINS_SPREADSHEET_ID = '190hLGCInKtdL0Jt50opJMRwb_bpKucf8M4drS7JvnyQ'  # mouse_strains

# ケージ情報を保持する辞書
cage_dict = {}

# ケージデータをスプレッドシートから読み込む関数
def load_cage_data():
    result = sheet.values().get(
        spreadsheetId=CAGE_DATA_SPREADSHEET_ID,
        range='Sheet1!A2:K'
    ).execute()
    values = result.get('values', [])
    cages = []
    for row in values:
        try:
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
        except (ValueError, IndexError) as e:
            print(f"Error parsing row: {row} - {e}")
            continue
    return cages

def save_cage_data(cages):
    values = []
    for cage in cages:
        values.append([
            str(cage['rack']),
            str(cage['row']),
            str(cage['col']),
            cage['cage_id'],
            cage['strain'],
            str(cage['count']),
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

# ケージデータを削除する関数
def delete_cage_data(rack, row, col):
    result = sheet.values().get(
        spreadsheetId=CAGE_DATA_SPREADSHEET_ID,
        range='Sheet1!A2:K'  # データの範囲
    ).execute()
    values = result.get('values', [])
    updated_values = [v for v in values if not (v[0] == rack and int(v[1]) == row and int(v[2]) == col)]
    
    body = {
        'values': updated_values
    }
    sheet.values().clear(
        spreadsheetId=CAGE_DATA_SPREADSHEET_ID,
        range='Sheet1!A2:K'
    ).execute()  # まず全てをクリア
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
        range='Sheet1!A2:B'  # データの範囲
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

# フォームクラスの定義
class CageForm(FlaskForm):
    cage_id = StringField('Cage ID', validators=[DataRequired()])
    user = SelectField('User', validators=[DataRequired()], choices=[])
    strain = SelectField('Mouse Strain', validators=[DataRequired()], choices=[])
    count = IntegerField('Number of Mice', validators=[DataRequired()])
    gender = SelectField('Gender', validators=[DataRequired()], choices=[('Male', 'Male'), ('Female', 'Female')])
    usage = SelectField('Usage', validators=[DataRequired()], choices=[('Maintain', 'Maintain'), ('Breeding', 'Breeding'), ('Experiment', 'Experiment'), ('New born', 'New born')])
    dob = StringField('DOB (MM-DD-YYYY)')
    note = TextAreaField('Note')
    submit = SubmitField('Save')

# アプリケーション起動時にデータをロード
def load_data():
    cages = load_cage_data()
    cage_dict.clear()  # データを再読み込みする際に辞書をクリア
    for cage in cages:
        key = (cage['rack'], cage['row'], cage['col'])
        cage_dict[key] = cage
    print("Loaded cages:")
    for key, cage in cage_dict.items():
        print(f"Key: {key}, Cage: {cage}")
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

    # ケージを座標で検索しやすいように辞書に変換
    cage_grid = {}
    for cage in rack_cages:
        key = (cage['row'], cage['col'])
        cage_grid[key] = cage

    return render_template('index.html',
                           rack_names=['A', 'B', 'C', 'D', 'E'],
                           current_rack=current_rack,
                           cages=rack_cages,
                           cage_grid=cage_grid,
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

    form = CageForm()

    # ユーザーリストと系統リストをフォームに設定
    form.user.choices = [(user, user) for user in user_list]
    form.strain.choices = [(strain, strain) for strain in strain_list]

    if request.method == 'POST' and form.validate():
        cage['cage_id'] = form.cage_id.data
        cage['user'] = form.user.data
        cage['strain'] = form.strain.data
        cage['count'] = form.count.data
        cage['gender'] = form.gender.data
        cage['usage'] = form.usage.data
        cage['dob'] = form.dob.data
        cage['note'] = form.note.data

        # DOBの処理を更新
        if cage['usage'] == 'New born':
            dob = cage['dob']
            if dob:
                # 正規表現でMM-DD-YYYY形式を検証
                if not re.match(r'^\d{2}-\d{2}-\d{4}$', dob):
                    flash("Please enter DOB in MM-DD-YYYY format.")
                    return redirect(request.url)
                try:
                    # 日付の妥当性を確認
                    dob_datetime = datetime.strptime(dob, '%m-%d-%Y')
                    # 必要に応じて別の形式に変換（例: MMDDYYYY）
                    cage['dob'] = dob_datetime.strftime('%m%d%Y')
                except ValueError:
                    flash("Invalid date. Please enter a valid DOB.")
                    return redirect(request.url)
            else:
                flash("DOB is required for 'New born' usage.")
                return redirect(request.url)
        else:
            cage['dob'] = ''  # 'New born' 以外の場合は DOB をクリア

        cage_dict[key] = cage
        save_cage_data(list(cage_dict.values()))
        load_data()  # データを再読み込み

        return redirect(url_for('index', rack=rack))

    else:
        # フォームに既存のケージ情報を設定
        form.cage_id.data = cage['cage_id']
        form.user.data = cage['user']
        form.strain.data = cage['strain']
        form.count.data = cage['count']
        form.gender.data = cage['gender']
        form.usage.data = cage['usage']
        form.dob.data = cage.get('dob', '')
        form.note.data = cage.get('note', '')

    return render_template('cage_detail.html',
                           rack=rack,
                           row=row,
                           col=col,
                           form=form)

# ケージを空にするためのルート
@app.route('/empty_cage/<rack>/<int:row>/<int:col>', methods=['POST'])
def empty_cage(rack, row, col):
    key = (rack, row, col)
    if key in cage_dict:
        del cage_dict[key]
        delete_cage_data(rack, row, col)  # スプレッドシートからも削除
        save_cage_data(list(cage_dict.values()))
        load_data()  # データを再読み込み
    return redirect(url_for('index', rack=rack))

# ケージの位置を入れ替えるためのルート
@app.route('/swap_cages', methods=['POST'])
@csrf.exempt  # CSRF トークンを検証しない
def swap_cages():
    data = request.get_json()
    rack = data['rack']
    source_row = int(data['source_row'])
    source_col = int(data['source_col'])
    target_row = int(data['target_row'])
    target_col = int(data['target_col'])

    source_key = (rack, source_row, source_col)
    target_key = (rack, target_row, target_col)

    # ケージ情報を取得
    source_cage = cage_dict.get(source_key)
    target_cage = cage_dict.get(target_key)

    # ケージの位置を入れ替え
    if source_cage:
        source_cage['row'] = target_row
        source_cage['col'] = target_col
        cage_dict[target_key] = source_cage
        del cage_dict[source_key]
    if target_cage:
        target_cage['row'] = source_row
        target_cage['col'] = source_col
        cage_dict[source_key] = target_cage
        del cage_dict[target_key]

    save_cage_data(list(cage_dict.values()))
    load_data()

    return jsonify({'status': 'success'}), 200

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
    strains = {}
    for cage in user_cages:
        strain = cage['strain']
        if strain not in strains:
            strains[strain] = {'total_mice': 0, 'cage_count': 0}
        strains[strain]['total_mice'] += cage['count']
        strains[strain]['cage_count'] += 1

    return render_template('summary.html',
                           user=user,
                           total_cages=total_cages,
                           total_mice=total_mice,
                           strains=strains)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
