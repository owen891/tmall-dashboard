"""
Repository 基类 — 提供通用 CRUD 和分页查询。
所有 repo 继承此类，减少重复代码。
"""
from models import db


class BaseRepo:
    model = None  # 子类设置

    @classmethod
    def get_by_id(cls, record_id):
        return cls.model.query.get(record_id)

    @classmethod
    def get_by_field(cls, **kwargs):
        return cls.model.query.filter_by(**kwargs).first()

    @classmethod
    def list_all(cls, **kwargs):
        return cls.model.query.filter_by(**kwargs).all()

    @classmethod
    def create(cls, **kwargs):
        record = cls.model(**kwargs)
        db.session.add(record)
        db.session.commit()
        return record

    @classmethod
    def update(cls, record_id, **kwargs):
        cls.model.query.filter_by(id=record_id).update(kwargs)
        db.session.commit()

    @classmethod
    def delete(cls, record_id):
        cls.model.query.filter_by(id=record_id).delete()
        db.session.commit()

    @classmethod
    def paginate(cls, query, page=1, per_page=20):
        """分页查询"""
        return query.paginate(page=page, per_page=per_page, error_out=False)
