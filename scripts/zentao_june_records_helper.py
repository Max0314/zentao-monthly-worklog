import json
import os
import urllib.request


BASE_API = "http://10.70.33.19/biz/api.php/v1"
ACCOUNT = os.environ.get("ZENTAO_ACCOUNT", "")
PASSWORD = os.environ.get("ZENTAO_PASSWORD", "")

# 2026-06-29 批量创建记录。
# 注意：本脚本不保存密码，运行前设置环境变量 ZENTAO_PASSWORD。
# 用途：复查本次创建记录状态、备注数量，或后续扩展为补备注脚本。
CREATED_TASKS = {
    4058: {
        88926: "SOP 旧版 Excel 与格式更新解析兼容能力完善",
        88927: "SOP 格式更新匹配保留与标准库字段合并能力完善",
        88928: "SOP 导出布局规则、模板排版与工具图片槽位能力完善",
        88929: "SOP 最终版直传、终版编辑与模板治理闭环完善",
        88930: "SOP 工位文本 AI 建议与操作步骤 AI 辅助能力建设",
        88931: "SOP BOP 工艺流程导入与流程匹配草稿能力建设",
        88932: "SOP 名称备注、记录重命名与列表展示能力完善",
        88933: "SOP 库学习质量门禁、标准库治理与工位发布能力完善",
        88934: "SOP 动作分析内部接口与工位候选上下文能力建设",
    },
    2826: {
        88935: "AI 周报生成流程与 Notable 数据接入能力建设",
        88936: "周报 metrics v2、三页 PNG 与公开看板能力建设",
        88937: "周报审批配置、结论编辑与钉钉机器人多群推送闭环",
        88938: "禅道 10 分制、质量分与备注评分口径建设",
        88939: "BI 综合看板多源数据同步、缓存预热与同步告警建设",
        88940: "Teambition 任务看板、积分矩阵与不纳入名单管理能力建设",
        88941: "酷学院考核看板、组织下钻与月度统计能力建设",
        88942: "硬件 AI 工具用量接入综合积分与看板能力建设",
        88943: "专利助手 BI 看板、人员名册推送与组织钻取能力建设",
        88944: "员工组织管理中心与部门可见性配置能力建设",
        88945: "Neocoder 插件用量同步、版本切换与下钻看板建设",
        88946: "BI 智能问答与钉钉 Agent Chat 能力建设",
        88947: "月度通知提醒与填报历史管理体验优化",
    },
    3248: {
        88948: "AI 专利助手资料导入、派生生成与自动配图能力建设",
    },
    1708: {
        88949: "代码评审组织趋势、代码量与申诉识别能力完善",
    },
}

CREATED_BUGS = {
    4058: {
        63812: "SOP 旧版 Excel/xls 解析兼容不足导致上传失败或字段缺失",
        63813: "SOP 格式更新页面动态 onclick 转义导致交互异常",
        63814: "SOP 上传流程工种分类丢失导致匹配结果偏差",
        63815: "SOP 生成步骤导航状态不稳导致流程跳转异常",
        63816: "SOP 操作步骤 AI 辅助延迟过高或边界兜底不足",
        63817: "SOP 学习审核与步骤 AI 边界数据导致标准库污染",
        63818: "SOP 工位发布脏数据导致工具或工艺要求展示异常",
        63819: "SOP 上传工序流程步骤丢失导致生成内容不完整",
        63820: "SOP 源步骤图片引用丢失导致生成草稿缺图",
        63821: "SOP 人工工具修改审批后未持久化导致工具库回退",
        63822: "SOP 最终版审批自动同步标准库导致标准库污染",
        63823: "SOP 记录列表载荷过大导致历史记录页面加载卡顿",
        63824: "SOP 最终版质量守护与返修发布摘要脏数据导致审核异常",
    },
    2826: {
        63825: "AI 周报 Notable 链接、权限、分页或 AI 解析异常导致生成失败",
        63826: "周报日期分桶和助手排名表达式错误导致指标偏差",
        63827: "周报看板窄屏布局与当前周生成异常",
        63828: "评审源库瞬断导致事实表清空或漏月低报",
        63829: "Assistant 同步失败中止整个 sync job 导致多源数据不同步",
        63830: "禅道质量分被未评分创建项、旧动作或解决备注口径拉偏",
        63831: "禅道身份别名和 LIMS 名称分桶不一致导致月度分归属错误",
        63832: "Teambition 删除/幽灵/历史逾期任务过滤异常导致积分不准",
        63833: "Teambition 综合看板 TB 列显示 0 或月度分缓存过慢",
        63834: "酷学院月份范围、静态资源或字段展示异常导致看板不准",
        63835: "员工组织 leader 索引超限或未分配行展示导致组织筛选异常",
        63836: "AI 分看板下钻点击和返回路径异常导致部门分析中断",
        63837: "绩效计划重算时计划项丢失导致评分明细异常",
        63838: "专利 BI 环境变量和部门映射异常导致组织统计偏差",
        63839: "硬件 AI 工具计分来源状态不可见导致积分难以核验",
    },
    3248: {
        63840: "AI 专利助手智能撰写占位和系统自产文字回流导致文档异常",
        63841: "AI 专利助手图表渲染清洗与 Word 带图导出异常",
        63842: "AI 专利助手灵感分析误触发 NEW_IDEA 与模型切换解析异常",
    },
    1708: {
        63843: "代码评审申诉负责人身份匹配不完整导致认领失败",
        63844: "代码评审组织趋势回填与缓存口径异常导致图表不准",
    },
}


def api_json(method, path, token, payload=None):
    data = None
    headers = {"Token": token}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=True).encode("ascii")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(BASE_API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def get_token():
    payload = {"account": ACCOUNT, "password": PASSWORD}
    data = json.dumps(payload, ensure_ascii=True).encode("ascii")
    req = urllib.request.Request(
        BASE_API + "/tokens",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["token"]


def verify_created_records():
    token = get_token()
    rows = []

    for execution, tasks in CREATED_TASKS.items():
        listed = api_json("GET", f"/executions/{execution}/tasks?limit=300", token).get("tasks", [])
        by_id = {int(item["id"]): item for item in listed}
        for task_id, title in tasks.items():
            item = by_id.get(task_id) or api_json("GET", f"/tasks/{task_id}", token)
            rows.append(
                {
                    "type": "task",
                    "execution": execution,
                    "id": task_id,
                    "expected_title": title,
                    "status": item.get("status"),
                    "title": item.get("name"),
                }
            )

    for execution, bugs in CREATED_BUGS.items():
        listed = api_json("GET", f"/executions/{execution}/bugs?limit=300", token).get("bugs", [])
        by_id = {int(item["id"]): item for item in listed}
        for bug_id, title in bugs.items():
            item = by_id.get(bug_id) or api_json("GET", f"/bugs/{bug_id}", token)
            rows.append(
                {
                    "type": "bug",
                    "execution": execution,
                    "id": bug_id,
                    "expected_title": title,
                    "status": item.get("status"),
                    "resolution": item.get("resolution"),
                    "title": item.get("title"),
                }
            )

    return rows


if __name__ == "__main__":
    for row in verify_created_records():
        print(json.dumps(row, ensure_ascii=False))
