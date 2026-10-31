from pathlib import Path
import json
ROOT=Path('/workspace')
source=ROOT/'app/frontend/tests/tests/results.json'
d=json.loads(source.read_text())
def specs(suites):
    return [item for suite in suites for item in suite.get('specs', []) + specs(suite.get('suites', []))]
rows=specs(d['suites'])
modules=['导航','项目','输入','计划','构建','预览','版本']
lines=['# 测试执行记录','', '日期：2026-10-31｜作者：Alex｜仅单元和集成两层｜无强制外部审阅门禁','',
'## 1. 实际命令与运行环境','',
'前端目录执行：`pnpm exec playwright test --config tests/studio.config.ts`。配置单worker，56个测试（单元21、集成35），JSON证据位于app/frontend/tests/tests/results.json；首次失败证据保存在tests/results-first.json。可用`--grep 单元`或`--grep 集成`选择同一入口的两层，不增加第三层。','',
'测试宿主testing/studio_app.py只在studio_test_t1命名空间建立并重置三张业务表。/__test/reset逐例清空隔离表、重置序号和故障状态，不触碰public生产数据。测试HTTP请求访问真实Studio路由、SQLAlchemy和PostgreSQL；AI输出固定mock。UI集成页面通过真实SDK访问测试宿主；单元页面静态渲染、外部回调替身，类使用受控Promise，不访问业务服务。','',
'## 2. 最新运行结果','',
'| 模块 | 单元通过/失败/未执行 | 集成通过/失败/未执行 |','|---|---|---|']
for module in modules:
    counts=[]
    for layer in ['单元','集成']:
        tests=[t for s in rows if s['title'].startswith(f'{module}-{layer}-') for t in s['tests']]
        counts.append('/'.join(str(sum(t['status']==status for t in tests)) for status in ['expected','unexpected','skipped']))
    lines.append(f'| {module} | {counts[0]} | {counts[1]} |')
lines+=['',f"总计：通过{d['stats']['expected']}，失败{d['stats']['unexpected']}，未执行/跳过{d['stats']['skipped']}。执行时长约{d['stats']['duration']/1000:.1f}秒。该统计只对应脚本断言，不推导历史设计所有子情景均通过。",'', '### 失败证据']
failed=False
for s in rows:
 for t in s['tests']:
    if t['status']=='unexpected':
      failed=True
      error=t['results'][-1].get('error',{}).get('message','失败无详细消息')
      error=error.split('Call log:')[0][:500].replace('\n',' ')
      lines.append(f"- {s['title']}：{error}")
if not failed:lines.append('- 本次脚本没有失败；不代表下列未覆盖子情景通过。')
lines+=['','## 3. 启动与修正历史','',
'- 初次启动：测试服务相对目录错误，未执行产品用例；改为明确cwd。',
'- 首次完整尝试：18通过、38失败。前半页面测试缺匹配Chromium可执行文件；容量用例60秒超时；构建后错误等待空输入提交按钮enabled；静态单元JSX被测试运行器转为非React对象。',
'- 修正：安装Chromium，配置240秒用例上限；用输入框可编辑判断busy结束；显式使用tsconfig.app.json的react-jsx编译设置。保留初次结果，不抹去失败。','',
'## 4. 已验证业务与未覆盖子情景','',
'脚本包含共享无登录入口、初始化顺序、项目写读删除、输入快捷键/长文本、确认后保存、两轮/历史不变、批准去重、失败重试、busy控件、预览计数/刷新/外开、恢复归属和部分成功读取重试。是否通过以表及失败条目为准。',
'',
'明确未执行或未充分覆盖：原设计所有重复实例/全部延迟阶段逐控件排列；200%缩放与完整键盘遍历；60秒Blob回收断言；任意iframe脚本异常；窗口资源卸载；计划/消息401容量的全部边界逐项；模拟HTML视觉/业务满足度。静态页面单元不验证真实点击、剪贴板调用和定时器；这些实际点击主要由集成覆盖。响应丢失后的项目/消息核对逻辑已实现，但没有专门丢响应自动化断言；超400消息核对受既有容量限制。真实AI及质量评估明确排除，未执行不视为本阶段产品失败。',
'',
'## 5. 其他验证','',
'Python语法检查：`python -m py_compile`检查routers/studio.py、services/studio_output.py、testing/studio_app.py。前端：`pnpm run lint && pnpm run build`。最新状态由最终验证登记补充。界面渲染检查单独登记，不替代两层结果。',
'',
'## 6. 产品与数据边界','',
'未修改生产三表结构或平台受保护模块；Studio业务路径不检查身份、不按user_id过滤，新记录studio-shared非凭据标识。列表维持最近60项目、最早400消息，无分页与跨标签锁；草稿刷新不保证。默认mock不实际调用真实提供者。部署与Cloud只占位，不是真实发布或管理功能。']
(ROOT/'docs/测试执行记录.md').write_text('\n'.join(lines)+'\n')
print(d['stats'])
for line in lines:
 if line.startswith('| '):print(line)
