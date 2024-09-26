from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # フォームのセキュリティに必要

# PostgreSQL データベース URI の設定（Render の PostgreSQL 接続情報に置き換える）
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://<username>:<password>@<host>:<port>/<dbname>'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 変更追跡機能を無効にする（推奨）

# SQLAlchemy の初期化
db = SQLAlchemy(app)

# ケージ情報を保持するテーブル定義
class Cage(db.Model):
    __tablename__ = 'cages'
    id = db.Column(db.Integer, primary_key=True)
    rack = db.Column(db.String(1), nullable=False)
    row = db.Column(db.Integer, nullable=False)
    col = db.Column(db.Integer, nullable=False)
    cage_id = db.Column(db.String(50), nullable=False)
    strain = db.Column(db.String(50), nullable=False)
    count = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    usage = db.Column(db.String(20), nullable=False)
    user = db.Column(db.String(50), nullable=False)
    dob = db.Column(db.String(20), nullable=True)
    note = db.Column(db.Text, nullable=True)

# データベースのテーブル作成
with app.app_context():
    db.create_all()

# データ表示用のルート
@app.route('/')
def index():
    # 現在のラックを取得（デフォルトはラックA）
    current_rack = request.args.get('rack', 'A')
    # 選択されたユーザーのフィルター
    selected_user = request.args.get('user', None)

    # ケージ情報をフィルタリング
    if selected_user:
        cages = Cage.query.filter_by(rack=current_rack, user=selected_user).all()
    else:
        cages = Cage.query.filter_by(rack=current_rack).all()

    # ラック内のケージ数とマウス数を計算
    filled_cages = len(cages)
    total_mice = sum(cage.count for cage in cages)

    # 全体のケージ数とマウス数を計算
    total_filled_cages = Cage.query.count()
    total_mice_all = db.session.query(db.func.sum(Cage.count)).scalar()

    return render_template('index.html',
                           rack_names=['A', 'B', 'C', 'D'],
                           current_rack=current_rack,
                           cages=cages,
                           filled_cages=filled_cages,
                           total_mice=total_mice,
                           total_filled_cages=total_filled_cages,
                           total_mice_all=total_mice_all,
                           user_list=Cage.query.distinct(Cage.user).all(),
                           selected_user=selected_user)

# ケージの詳細表示と編集用のルート
@app.route('/cage/<rack>/<int:row>/<int:col>', methods=['GET', 'POST'])
def cage_detail(rack, row, col):
    cage = Cage.query.filter_by(rack=rack, row=row, col=col).first()
    if not cage:
        cage = Cage(rack=rack, row=row, col=col)

    if request.method == 'POST':
        cage.cage_id = request.form['cage_id']
        cage.user = request.form['user']
        cage.strain = request.form['strain']
        cage.count = request.form['count']
        cage.gender = request.form['gender']
        cage.usage = request.form['usage']
        cage.dob = request.form.get('dob', '')
        cage.note = request.form.get('note', '')

        if not cage.cage_id or not cage.user or not cage.strain or not cage.count or not cage.gender or not cage.usage:
            flash("Please fill in all required fields.")
            return redirect(request.url)
        if not cage.count.isdigit():
            flash("Number of Mice must be a positive integer.")
            return redirect(request.url)
        if cage.usage == "New born" and not cage.dob:
            flash("Please provide DOB for New born mice.")
            return redirect(request.url)

        db.session.add(cage)
        db.session.commit()

        return redirect(url_for('index', rack=rack))

    return render_template('cage_detail.html',
                           rack=rack,
                           row=row,
                           col=col,
                           cage_info=cage,
                           strain_list=['Strain1', 'Strain2', 'Strain3'],  # 実際の系統リストを指定
                           user_list=['User1', 'User2', 'User3'])  # 実際のユーザーリストを指定

# ケージを空にするためのルート
@app.route('/empty_cage/<rack>/<int:row>/<int:col>', methods=['POST'])
def empty_cage(rack, row, col):
    cage = Cage.query.filter_by(rack=rack, row=row, col=col).first()
    if cage:
        db.session.delete(cage)
        db.session.commit()
    return redirect(url_for('index', rack=rack))

# ユーザーサマリーの表示
@app.route('/summary', methods=['GET'])
def summary():
    user = request.args.get('user', '')
    if not user:
        flash("Please select a user.")
        return redirect(url_for('index'))

    user_cages = Cage.query.filter_by(user=user).all()
    total_cages = len(user_cages)
    total_mice = sum(cage.count for cage in user_cages)
    strains = {cage.strain for cage in user_cages}

    return render_template('summary.html',
                           user=user,
                           total_cages=total_cages,
                           total_mice=total_mice,
                           strains=strains)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
