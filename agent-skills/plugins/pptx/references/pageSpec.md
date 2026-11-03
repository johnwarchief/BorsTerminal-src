# PageSpec 接入边界

完整视觉规范、形状集合和样式/提纲/页面提示词见 [生成参考](generation.md)。这里补充 Qoder Office 的工具接入规则，不维护另一份设计规范。

- 优先用 `page` 传单页对象 `{"background":"#RRGGBB","elements":[...]}`；旧 `pageSpec` 接受同一内容的 JSON 字符串，两者不能同时传。不包在 `{"slides":[...]}` 中。支持文字、形状、图片。原生图表和表格通过 `apply_ops` 在生成页面后插入，不属于 PageSpec 元素类型。
- 几何使用 1280×720 px，元素有数值 `x,y,w,h`，宽高为正且不出界，最多 48 个元素。`sizePt` 使用 pt，不能直接填入设计稿的 px 字号。数组从底到顶绘制，正文放在背景和装饰之后。
- 第一页用 `begin_deck`，后续用 `put_page`；已有文稿先 `read_context`，确认画布支持及最新页序。新文稿创建前不读取一个尚不存在的路径。
- 可选 `imageFiles` 也是 JSON 字符串，键为 PageSpec 图片 URL，值为授权的本地 PNG/JPEG 绝对路径。引擎按图片框等比居中裁剪，不会隐式下载。不可用图片会使本页整体失败。
- 读取已有内容用 `read_slide`；局部文字、字体与几何调整用 `execute_slide_script`，不要为微调而用 `put_page` 替换整页。只有用户要求重做页面时才重新设计该页。
- 每次写入使用工具返回的最新 revision 与唯一 operationId，最后 `check_deck` 并 `save_document`。工具参数以当前完整定义为准。
