"""HTTP 接口的请求 / 响应模型。

这里只描述「接口长什么样」，不碰数据库。和 app/models.py 的区别：

    models.py        表结构，SQLAlchemy 管，只关心怎么存
    schemas/*.py     接口契约，Pydantic 管，只关心怎么传

所以给表加一列不会自动出现在接口里；想暴露什么字段，在这里显式写。
"""
