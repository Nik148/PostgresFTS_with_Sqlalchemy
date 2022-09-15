from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TSVECTOR

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:<password>@<server>:<port>/<database>"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    lang = db.Column(db.String(30))
    # Колонка, в которой хранится tsvector
    body_vector = db.Column(TSVECTOR)

    # Создаем индекс gin
    __table_args__ = (
        db.Index(
            'ix_body_vector',
            body_vector,
            postgresql_using='gin'
            ),
        )

    @staticmethod
    # Преобразует строку в tsvector
    def to_tsvector(text, lang):
        # Для преобразования строки в tsvector отправляем запрос to_tsvector в Postgres
        # Возможно есть какой то другой способ для преобразования
        body_vect = db.session.query(func.to_tsvector(lang, text)).first()[0]
        return body_vect
        

    @staticmethod
    # Добавляем пост
    def add_post(text, lang):
        post = Post(body=text, body_vector=Post.to_tsvector(text, lang), lang=lang)
        db.session.add(post)
        db.session.commit()

    # Поиск, возвращающий список объектов Post
    def search(expression, lang):    
        '''SELECT * FROM post
           WHERE "body_vector" @@ plainto_tsquery(lang, expression)
           ORDER BY ts_rank("body_vector", plainto_tsquery(lang, expression)) DESC;'''
        return Post.query.filter\
        (Post.body_vector.bool_op('@@')(func.plainto_tsquery(expression, postgresql_regconfig=lang)))\
        .order_by(func.ts_rank(Post.body_vector, func.plainto_tsquery(expression, postgresql_regconfig=lang))).all()

    # Поиск по префиксу, тоже возвращает список объектов Post
    def search_prefix(expression, lang):
        '''SELECT * FROM post
           WHERE "body_vector" @@ to_tsquery(lang, expression)
           ORDER BY ts_rank("body_vector", to_tsquery(lang, expression)) DESC;'''

        # Если у нас несколько слов в expression, то нужно между ними поставить логические элементы, иначе будет ошибка
        # Поэтому мы делим expression на список слова, а если у нас только одно слово, то заключаем его в список
        # А дальше с помощью join добавляем между словами лог.опер.'&'
        expression_list = expression.split() if ' ' in expression else [expression]
        return Post.query.filter\
        (Post.body_vector.bool_op('@@')(func.to_tsquery('&'.join(expression_list)+':*', postgresql_regconfig=lang)))\
        .order_by(func.ts_rank(Post.body_vector, func.to_tsquery('&'.join(expression_list)+':*', postgresql_regconfig=lang))).all()

        

if __name__ == '__main__':
    app.run(debug=True)