"""台股 ticker ↔ 公司中文名對照（R6 Ontology 子集，引用顯示用）。

對照來源（single source of truth）＝ ``docs/r6/ontology/seeds/company_dim.csv``
（= ``polaris_core.company_dim``）。因 ``docs/`` 被 ``.dockerignore`` 排除（容器內讀
不到 CSV），這裡以 Python literal 內嵌 20 列 canonical 對照；
``tests/test_company_names.py`` 對 seed CSV 做同步守門，任何一邊漂移即測試失敗。
"""
from .companies import company_label, company_name

__all__ = ["company_label", "company_name"]
