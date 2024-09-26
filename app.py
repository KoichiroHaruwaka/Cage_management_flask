from flask import Flask, render_template, request, redirect, url_for, flash
import csv
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # フォームのセキュリティに必要

# ケージ情報を保持する辞書
# キーは (rack, row, col) のタプル
cages = {}

# マウスの系統リストとユーザーリストを読み込む関数
def load_strains_and_users(filename="mouse_strains.csv"):
    strain_list = []
    user_list = []
    try:
        with open(filename, mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                strain = row.get("Strain", "")
                if strain and strain not in strain_list:
                    strain_list.append(strain)
                user = row.get("User", "")
                if user and user not in user_list:
                    user_list.append(user)
    except FileNotFoundError:
        pass
    return strain_list, user_list

# 系統リストとユーザーリストの読み込み
strain_list, user_list = load_strains_and_users()

# ラック名のリスト
rack_names = ['A', 'B', 'C', 'D']

# データをCSVに保存する関数
def save_to_csv(filename="cage_data.csv"):
    with open(filename, mode='w', newline='') as file:
        fieldnames = ["rack", "row", "col", "cage_id", "strain", "count", "gender", "usage", "user", "dob", "note"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for (rack, row, col), cage_info in cages.items():
            writer.writerow({
                "rack": rack,
                "row": row,
                "col": col,
                "cage_id": cage_info["cage_id"],
                "strain": cage_info["strain"],
                "count": cage_info["count"],
                "gender": cage_info["gender"],
                "usage": cage_info["usage"],
                "user": cage_info["user"],
                "dob": cage_info.get("dob", ""),
                "note": cage_info.get("note", "")
            })

# データをCSVからロードする関数
def load_from_csv(filename="cage_data.csv"):
    if not os.path.exists(filename):
        return
    with open(filename, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            rack = row["rack"]
            row_idx = int(row["row"])
            col_idx = int(row["col"])
            cages[(rack, row_idx, col_idx)] = {
                "cage_id": row["cage_id"],
                "strain": row["strain"],
                "count": row.get("count", "0") or "0",  # 修正
                "gender": row["gender"],
                "usage": row["usage"],
                "user": row.get("user", ""),
                "dob": row.get("dob", ""),
                "note": row.get("note", "")
            }

# アプリケーション起動時にデータをロード
load_from_csv()

@app.route('/')
def index():
    # 現在のラックを取得（デフォルトはラックA）
    current_rack = request.args.get('rack', 'A')
    # 選択されたユーザーのフィルター
    selected_user = request.args.get('user', None)
    # ケージ情報をフィルタリング
    rack_cages = {}
    for (rack, row, col), cage_info in cages.items():
        if rack == current_rack:
            if not selected_user or cage_info['user'] == selected_user:
                rack_cages[(row, col)] = cage_info
    # ラック内のケージ数とマウス数を計算
    filled_cages = len(rack_cages)
    total_mice = sum(int(info["count"] or 0) for info in rack_cages.values())  # 修正
    # 全体のケージ数とマウス数を計算
    total_filled_cages = len(cages)
    total_mice_all = sum(int(info["count"] or 0) for info in cages.values())  # 修正
    return render_template('index.html',
                           rack_names=rack_names,
                           current_rack=current_rack,
                           cages=rack_cages,
                           filled_cages=filled_cages,
                           total_mice=total_mice,
                           total_filled_cages=total_filled_cages,
                           total_mice_all=total_mice_all,
                           user_list=user_list,
                           selected_user=selected_user)

@app.route('/cage/<rack>/<int:row>/<int:col>', methods=['GET', 'POST'])
def cage_detail(rack, row, col):
    key = (rack, row, col)
    cage_info = cages.get(key, {
        "cage_id": "",
        "strain": strain_list[0] if strain_list else "",
        "count": "",
        "gender": "Male",
        "usage": "Maintain",
        "user": user_list[0] if user_list else "",
        "dob": "",
        "note": ""
    })
    if request.method == 'POST':
        cage_id = request.form['cage_id']
        user = request.form['user']
        strain = request.form['strain']
        count = request.form['count']
        gender = request.form['gender']
        usage = request.form['usage']
        dob = request.form.get('dob', '')
        note = request.form.get('note', '')
        # フォームのバリデーション
        if not cage_id or not user or not strain or not count or not gender or not usage:
            flash("Please fill in all required fields.")
            return redirect(request.url)
        if not count.isdigit():
            flash("Number of Mice must be a positive integer.")
            return redirect(request.url)
        if usage == "New born":
            if not dob:
                flash("Please provide DOB for New born mice.")
                return redirect(request.url)
            try:
                datetime.strptime(dob, "%m-%d-%Y")
            except ValueError:
                flash("DOB must be in MM-DD-YYYY format.")
                return redirect(request.url)
        else:
            dob = ""
        cages[key] = {
            "cage_id": cage_id,
            "user": user,
            "strain": strain,
            "count": count,
            "gender": gender,
            "usage": usage,
            "dob": dob,
            "note": note
        }
        save_to_csv()
        return redirect(url_for('index', rack=rack))
    return render_template('cage_detail.html',
                           rack=rack,
                           row=row,
                           col=col,
                           cage_info=cage_info,
                           strain_list=strain_list,
                           user_list=user_list)

@app.route('/empty_cage/<rack>/<int:row>/<int:col>', methods=['POST'])
def empty_cage(rack, row, col):
    key = (rack, row, col)
    if key in cages:
        del cages[key]
        save_to_csv()
    return redirect(url_for('index', rack=rack))

@app.route('/summary', methods=['GET'])
def summary():
    user = request.args.get('user', '')
    if not user:
        flash("Please select a user.")
        return redirect(url_for('index'))
    user_cages = [info for info in cages.values() if info["user"] == user]
    total_cages = len(user_cages)
    total_mice = sum(int(info["count"] or 0) for info in user_cages)  # 修正
    strains = set(info["strain"] for info in user_cages)
    return render_template('summary.html',
                           user=user,
                           total_cages=total_cages,
                           total_mice=total_mice,
                           strains=strains)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
