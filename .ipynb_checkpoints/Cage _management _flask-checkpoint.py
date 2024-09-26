#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from flask import Flask, render_template, request, redirect
import csv

app = Flask(__name__)

# データの読み込み関数
def load_cages():
    cages = []
    try:
        with open('cage_data.csv', mode='r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                cages.append(row)
    except FileNotFoundError:
        pass
    return cages

# データの書き込み関数
def save_cage(cage_id, strain, count, gender, usage):
    with open('cage_data.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([cage_id, strain, count, gender, usage])

# ホームページ
@app.route('/')
def index():
    cages = load_cages()
    return render_template('index.html', cages=cages)

# 新しいケージデータの保存
@app.route('/save', methods=['POST'])
def save_data():
    cage_id = request.form['cage_id']
    strain = request.form['strain']
    count = request.form['count']
    gender = request.form['gender']
    usage = request.form['usage']
    
    save_cage(cage_id, strain, count, gender, usage)
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)


