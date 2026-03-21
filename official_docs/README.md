# 公式ドキュメント

このディレクトリには永久保存する公式ドキュメントを配置する。

## 登録済みドキュメント

（自動更新）

## 追加方法

```python
python -c "
from rag_retriever import index_official_doc
index_official_doc(
    doc_id='doc_name',
    content=open('path/to/doc.md').read(),
    source='https://...',
    version='1.0',
)
"
```
