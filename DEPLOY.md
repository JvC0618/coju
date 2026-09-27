# 部署说明
本地运行参见README.md。本压缩包包含源码，不包含Python解释器、依赖环境或Key。

如需更新你们已有的Streamlit部署，将本包中的源码文件（包括新增cuisines.py）及requirements.txt整体更新到原仓库。不要仅覆盖app.py。
部署入口仍为app.py。选择Python 3.12。环境重建后先运行离线示例，再用自己的Key小规模验证真实模式。

可在部署平台的Secrets中配置AMAP_KEY；请勿提交到GitHub。也可让每位使用者在页面中输入自己的Key。
如果COJU_OFFLINE=1，则强制离线；需要实时查询时应移除此项或设置为0。
没有Key时离线示例可运行。即使有Key，界面默认仍为离线示例，避免打开页面就调用接口。

