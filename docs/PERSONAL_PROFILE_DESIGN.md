# 个人画像层详细设计文档

> 状态：设计稿，待评审。评审通过后按第七节阶段划分实施。
> 范围：资料输入 → 个人图谱 → 稳定个人模型。不涉及 Simulation、人生分支预测、原有五步流程。

---

## 一、总体架构

```
┌─ 前端（新增独立页面，不动原五步流程）─────────────────┐
│  量化基础信息表单 + 自由资料区（粘贴/上传）              │
└──────────────┬───────────────────────────┘
               │ POST /api/profile/*
┌─ 后端（新增 profile 蓝图）───────────────────────────┐
│  1. 资料预处理：结构化表单 → 带来源标注文本             │
│  2. 建图：固定个人本体 + GraphBuilderService（复用）    │
│  3. 画像合成：ProfileSynthesizer（新，LLM 三阶段）      │
│  4. 存储：personal_model.json（版本化快照）             │
└──────────────────────────────────────────────┘
```

核心原则：
- **图谱 = 事实库**（可增量补充资料、可溯源），**个人模型 = 稳定快照**（分支层唯一消费入口）
- 结构化数据与自由文本**同管线**（都格式化为文本进 Zep，避免双通道复杂度）
- 可信度分级：来源决定权重，冲突不丢弃、记入 `conflicts`

---

## 二、前端输入区设计

页面路由：`/profile/create` 与 `/profile/:projectId`（新页面，原路由不动）。

### 2.1 量化基础信息表单（结构化，约 5 分钟填完）

设计原则：**每个字段都可选**（缺什么由图谱和 LLM 补），但预置引导性选项降低填写成本。
字段全部为可选，未填写字段不进入合成输入。

#### A. 基本盘

| 字段 | 控件 | 选项/格式 | 说明 |
|---|---|---|---|
| 昵称/称呼 | 文本 | 自由 | 报告中如何称呼你 |
| 年龄段 | 下拉 | 18-24 / 25-30 / 31-35 / 36-45 / 46-55 / 56+ / 不便透露 | 段别即可，不强制精确年龄 |
| 性别 | 下拉 | 女 / 男 / 其他 / 不便透露 | |
| 所在城市 | 文本 | 自由 | 影响分支的环境变量 |
| 行业/职业方向 | 文本+常用建议 | 自由（输入联想：互联网/金融/教育/医疗…） | |
| 当前状态 | 单选 | 在职稳定 / 在职迷茫 / 求学 / 求职 / Gap / 创业 / 自由职业 | 分支起点的重要变量 |
| 学历阶段 | 下拉 | 高中及以下 / 大专 / 本科 / 硕士 / 博士 / 在读 | |

#### B. 性格与认知

| 字段 | 控件 | 选项/格式 | 说明 |
|---|---|---|---|
| MBTI | 16 宫格选择器 或 "不确定" | INTP… | 自评为最高置信来源 |
| 大五自评 | 5 条滑块（1-7） | 开放性/尽责性/外向性/宜人性/神经质 | 可整体跳过 |
| 自我描述标签 | 标签多选+自由输入 | 预置："执行力强""容易内耗""社恐但线上活跃""完美主义""冒险偏好""求稳" 等 20 个 | 快速勾勒，与 MBTI 互补 |

#### C. 能力与资源

| 字段 | 控件 | 格式 | 说明 |
|---|---|---|---|
| 技能清单 | 动态行 | {名称, 熟练度 1-5, 类型(专业/软技能/爱好)} | 可多行 |
| 语言能力 | 标签 | 自由 | 可选 |
| 财务状态 | 单选 | 宽裕 / 稳定有结余 / 紧平衡 / 压力大有负债 / 不便透露 | 强烈影响分支走向，默认"不便透露" |

#### D. 人际与支持网络

| 字段 | 控件 | 格式 | 说明 |
|---|---|---|---|
| 家庭状态 | 单选 | 单身 / 恋爱中 / 已婚 / 已婚有孩 / 其他 | |
| 社交支持度 | 滑块 1-5 | "遇到大事有人可商量"的程度 | |
| 重要关系人 | 动态行 | {称呼, 关系(家人/朋友/同事/导师), 亲密度1-5, 对我的影响一句话} | 分支层的关键 NPC |

#### E. 目标与困扰（自由文本，带引导 placeholder）

| 字段 | 引导语 |
|---|---|
| 近 1-3 年最想实现的事 | "比如：转行成功 / 存款到 X / 找到伴侣 / 出国…" |
| 当前最大的卡点 | "比如：不知道要不要辞职 / 精力被家庭占据 / 迷茫没方向…" |
| 明确不想要的 | "比如：不加班 / 不离开本城市 / 不做管理岗…" |

### 2.2 自由资料区

| 输入方式 | 说明 |
|---|---|
| 直接粘贴大段文字 | 无需文件，贴日记/感想即可 |
| 文件上传 | 复用现有 pdf/md/txt 解析 |
| 资料类型标签 | 每份资料必选：日记 / 感想随笔 / 简历 / 书单影单 / 聊天记录 / 其他 —— **标签决定可信度权重** |
| 时间范围（可选） | 如"2023-2024 的日记"，帮助 LLM 排时间线 |

### 2.3 可信度权重表（前后端共用约定）

```
结构化表单(0.95) > 简历(0.85) > 聊天记录(0.7)
              > 日记(0.6) > 感想随笔(0.55) > 书单影单/其他(0.4)
```

### 2.4 交互流

```
填表单(可只填一部分) → 可选:贴日记/传文件 → 点击「生成画像」
  → 建图进度条(复用现有任务轮询样式) → 画像合成进度
  → 画像页(简化版,见2.5) → 「补充资料重新生成」入口
```

### 2.5 画像预览页（简化版，已按评审反馈降低信息密度）

只保留三块，其余全部折叠：

1. **核心画像**：三行文本——"25-30 · 杭州 · 在职迷茫"、"INTP · 容易内耗但线上活跃"、"核心张力：稳定 vs 自由"（来自 `current_state`，一屏内看完）
2. **目标与卡点**：want / avoid 各一行 + 当前卡点一行（最多 3 行）
3. **折叠详情**（默认收起，点击展开）：时间线、技能、关系人、情绪模式、冲突与资料缺口——供愿意深挖的用户查看，不打扰快速浏览

原则：首屏不超过 6 行有效信息；所有 `conflicts` / `open_questions` 移入折叠区。

---

## 三、个人本体（固定预设，完整 JSON）

> 与 `OntologyGenerator.generate()` 输出格式完全一致，可直接传入
> `GraphBuilderService.set_ontology()`（[graph_builder.py:313](../backend/app/services/graph_builder.py)）。
> 属性名已避开 Zep 保留字（name/uuid/group_id/graph_id/created_at/summary）。

```json
{
  "entity_types": [
    {
      "name": "Person",
      "description": "The profile owner and every real person related to them (family, friends, colleagues, mentors).",
      "attributes": [
        {"name": "full_name", "type": "text", "description": "Name or nickname"},
        {"name": "relation_kind", "type": "text", "description": "self / family / friend / colleague / mentor / other"},
        {"name": "role", "type": "text", "description": "Occupation or social role"}
      ],
      "examples": ["the profile owner", "my mother", "college roommate"]
    },
    {
      "name": "Trait",
      "description": "Personality traits: MBTI type, Big Five facets, or descriptive traits.",
      "attributes": [
        {"name": "trait_kind", "type": "text", "description": "mbti / big5 / descriptive"},
        {"name": "evidence", "type": "text", "description": "Where this trait shows up"}
      ],
      "examples": ["INTP", "high openness", "procrastinates under low deadlines"]
    },
    {
      "name": "Value",
      "description": "Core values and beliefs that guide decisions.",
      "attributes": [
        {"name": "value_domain", "type": "text", "description": "career / family / money / freedom / security / recognition / life"},
        {"name": "stance", "type": "text", "description": "What the person believes in this domain"}
      ],
      "examples": ["freedom over stability", "family comes first"]
    },
    {
      "name": "Skill",
      "description": "Professional or soft skills with self-assessed proficiency.",
      "attributes": [
        {"name": "skill_domain", "type": "text", "description": "professional / soft / hobby"},
        {"name": "proficiency", "type": "text", "description": "beginner / intermediate / advanced / expert"}
      ],
      "examples": ["Python data analysis", "public speaking"]
    },
    {
      "name": "Interest",
      "description": "Hobbies and topics the person enjoys, including favorite books, films and content.",
      "attributes": [
        {"name": "interest_category", "type": "text", "description": "reading / film / sport / music / tech / other"},
        {"name": "intensity", "type": "text", "description": "casual / regular / deep"}
      ],
      "examples": ["science fiction novels", "bouldering", "psychology podcasts"]
    },
    {
      "name": "Experience",
      "description": "Any life experience segment: education, work, project, life event. Unified type, use experience_kind to distinguish.",
      "attributes": [
        {"name": "experience_kind", "type": "text", "description": "education / work / project / life"},
        {"name": "period", "type": "text", "description": "Time range, e.g. 2018-2022"},
        {"name": "outcome", "type": "text", "description": "How it ended or what it led to"}
      ],
      "examples": ["CS undergraduate 2018-2022", "first job at a startup 2022-2024"]
    },
    {
      "name": "Milestone",
      "description": "Key turning points, achievements or setbacks that changed the person's trajectory.",
      "attributes": [
        {"name": "milestone_kind", "type": "text", "description": "turning_point / achievement / setback"},
        {"name": "impact", "type": "text", "description": "What changed because of it"}
      ],
      "examples": ["failed the graduate exam", "got promoted to team lead"]
    },
    {
      "name": "Aspiration",
      "description": "Goals, wishes and unfinished business, including explicit things the person does NOT want.",
      "attributes": [
        {"name": "horizon", "type": "text", "description": "short_term / mid_term / long_term"},
        {"name": "polarity", "type": "text", "description": "want / want_to_avoid"},
        {"name": "feasibility_note", "type": "text", "description": "Constraints or conditions the person mentioned"}
      ],
      "examples": ["switch to data science within 2 years", "never work overtime-heavy jobs"]
    },
    {
      "name": "Organization",
      "description": "Schools, companies, cities and other places where experiences occurred. Fallback container type.",
      "attributes": [
        {"name": "org_name", "type": "text", "description": "Name of the organization, school, company or city"},
        {"name": "org_kind", "type": "text", "description": "school / company / city / community / other"}
      ],
      "examples": ["Tsinghua University", "a Hangzhou internet company", "Chengdu"]
    },
    {
      "name": "EmotionalPattern",
      "description": "Recurring emotional and psychological patterns observed mainly from diaries and reflections.",
      "attributes": [
        {"name": "pattern_kind", "type": "text", "description": "stress / motivation / mood / self_talk"},
        {"name": "trigger", "type": "text", "description": "What usually triggers this pattern"}
      ],
      "examples": ["Sunday-night anxiety before work weeks", "bursts of motivation after watching others succeed"]
    }
  ],
  "edge_types": [
    {
      "name": "EXPERIENCED",
      "description": "A person went through an experience.",
      "source_targets": [{"source": "Person", "target": "Experience"}],
      "attributes": []
    },
    {
      "name": "HAS_TRAIT",
      "description": "A person has a personality trait.",
      "source_targets": [{"source": "Person", "target": "Trait"}],
      "attributes": []
    },
    {
      "name": "HOLDS_VALUE",
      "description": "A person holds a value.",
      "source_targets": [{"source": "Person", "target": "Value"}],
      "attributes": []
    },
    {
      "name": "HAS_SKILL",
      "description": "A person has a skill.",
      "source_targets": [{"source": "Person", "target": "Skill"}],
      "attributes": []
    },
    {
      "name": "INTERESTED_IN",
      "description": "A person is interested in something.",
      "source_targets": [{"source": "Person", "target": "Interest"}],
      "attributes": []
    },
    {
      "name": "ASPIRES_TO",
      "description": "A person holds an aspiration (want or want_to_avoid).",
      "source_targets": [{"source": "Person", "target": "Aspiration"}],
      "attributes": []
    },
    {
      "name": "CONNECTED_TO",
      "description": "Interpersonal relationship between two persons.",
      "source_targets": [{"source": "Person", "target": "Person"}],
      "attributes": [
        {"name": "closeness", "type": "text", "description": "close / regular / distant"}
      ]
    },
    {
      "name": "OCCURRED_AT",
      "description": "An experience happened at an organization or place.",
      "source_targets": [{"source": "Experience", "target": "Organization"}],
      "attributes": []
    },
    {
      "name": "INVOLVED",
      "description": "A person or experience involves an organization.",
      "source_targets": [
        {"source": "Person", "target": "Organization"},
        {"source": "Experience", "target": "Organization"}
      ],
      "attributes": []
    },
    {
      "name": "LED_TO",
      "description": "An experience or milestone caused or led to another milestone. Causal chain, key material for future branch simulation.",
      "source_targets": [
        {"source": "Experience", "target": "Milestone"},
        {"source": "Milestone", "target": "Milestone"}
      ],
      "attributes": []
    }
  ],
  "analysis_summary": "Personal profile ontology: fixed preset, not LLM-generated."
}
```

实体数 10、边数 10，恰好满足 `MAX_ONTOLOGY_TYPES` 上限。

---

## 四、资料预处理规范

### 4.1 结构化表单 → 文本

每个分区渲染为带元数据的文本块（Python 端一个纯函数）：

```
=== [结构化输入 | 来源: 量化表单 | 置信度: 0.95] ===
【基本盘】年龄段: 25-30; 城市: 杭州; 行业: 互联网; 当前状态: 在职迷茫; 学历: 本科
【性格】MBTI: INTP; 大五: 开放性6 尽责性4 外向性2 宜人性5 神经质5; 标签: 容易内耗, 线上活跃
【能力】技能: Python(4/5,专业), SQL(3/5,专业); 财务状态: 紧平衡
【人际】家庭状态: 单身; 社交支持度: 3/5; 重要关系人: 母亲(家人,亲密度5,"希望我考编")
【目标】1-3年: 转行数据分析; 卡点: 不敢裸辞,存款不够; 不想要: 加班多的岗位
```

### 4.2 自由资料 → 文本

```
=== [日记 | 来源: 用户粘贴 | 时间范围: 2024全年 | 置信度: 0.6] ===
（原文，按 500/50 切块后进 Zep）
```

### 4.3 增量补料

- 同一 `graph_id` 追加新 Batch ingestion（Zep Batch API 天然支持）
- `materials_manifest.json` 记录每份资料的 hash/类型/时间，防止重复提交
- 重新合成时基于全部实体（图谱幂等），个人模型 `model_version + 1`

---

## 五、画像合成器（ProfileSynthesizer）

### 5.1 三阶段合成流程

```
阶段1 快照分区   : basic_info / personality / values / skills / interests / emotional_patterns
阶段2 叙事分区   : timeline / milestones / relationships / aspirations
阶段3 综合判断   : current_state / conflicts / source_coverage / open_questions
```

每个阶段：`ZepEntityReader` 按类型取实体 → 关键实体 `graph.search` 补事实 → LLM 合成对应分区。
阶段间通过"阶段3 综合前两阶段产出"保证一致性。
每阶段一次 LLM 调用（`llm_client.chat_json`，复用重试），共 3 次主调用。

### 5.2 系统提示词（阶段1示例）

```
你是一位资深的用户研究员与心理测量分析师。你将收到一个人的人生资料所构建的知识图谱
中提取的实体与事实（已按类型分组）。请把它们合成为结构化的个人画像分区。

铁律：
1. 每个结论必须标注 source（structured_form / resume / diary / reflection / preference / inference）
2. 图谱中没有的信息不要编造；可基于多处证据做温和推断，但必须标 source: "inference"
3. 用户的自我评价与行为证据是两个维度：自评写入 self_view，行为证据写入 observed，不要互相覆盖
4. 出现矛盾时：按置信度权重裁决主结论，但把矛盾原样记入 conflicts 数组
5. 情绪化表述（如"我一事无成"）不作为事实采纳，转换为 emotional_patterns 线索
6. 输出严格 JSON，结构如下：
{ ...当前分区的 schema... , "conflicts": [{"field":"","views":[],"resolution":""}] }
```

### 5.3 冲突消解规则表

| # | 冲突类型 | 处理规则 |
|---|---|---|
| 1 | 客观事实冲突（学历/经历/时间） | 高置信来源获胜（表单>简历>日记），冲突入 conflicts |
| 2 | 性格自评 vs 行为证据 | 不裁决：自评入 `personality.self_view`，行为入 `personality.observed` |
| 3 | MBTI 自填 vs 日记表现矛盾 | 自填为准；矛盾时 `confidence: "low"` + conflicts 记录证据 |
| 4 | 大五滑块 vs 描述性标签矛盾 | 数值与标签都保留，由阶段3 综合评注 |
| 5 | 情绪化极端评价 | 不采纳为能力/状态事实，转 emotional_pattern，保留原文于 evidence |
| 6 | 时间线断裂（gap） | 不臆造，timeline 中显式标注 `{"period":"2020-2021","kind":"gap"}` |
| 7 | 目标 vs "不想要"冲突（想转行又怕风险） | 正常状态不是错误：aspirations 同时保留 want 与 want_to_avoid，阶段3 在 current_state 中点明张力 |

### 5.4 个人模型完整 Schema

```json
{
  "model_version": 1,
  "project_id": "proj_xxx",
  "graph_id": "prism_xxx",
  "content_hash": "sha256(全部合成输入)",
  "created_at": "ISO8601",

  "basic_info": {
    "age_range": "25-30", "gender": null, "location": "杭州",
    "industry": "互联网", "current_status": "在职迷茫",
    "education_level": "本科", "financial_state": "紧平衡"
  },
  "personality": {
    "mbti": {"value": "INTP", "confidence": "high", "conflict_note": null},
    "big5": {"openness": 6, "conscientiousness": 4, "extraversion": 2, "agreeableness": 5, "neuroticism": 5},
    "self_view": [{"trait": "内耗", "source": "structured_form"}],
    "observed": [{"trait": "对感兴趣领域爆发式投入", "source": "diary", "evidence": "连续三周记录自学到凌晨"}]
  },
  "values": [{"domain": "freedom", "stance": "不愿被管束", "source": "diary"}],
  "skills": [{"name": "Python", "domain": "professional", "proficiency": "intermediate", "source": "resume"}],
  "interests": [{"category": "reading", "item": "科幻小说", "intensity": "deep", "source": "preference"}],
  "emotional_patterns": [
    {"pattern_kind": "stress", "trigger": "周日晚想到上班", "source": "diary", "evidence": "2024年约40%日记提及"}
  ],

  "timeline": [
    {"period": "2018-2022", "kind": "education", "summary": "本科 计算机相关", "outcome": "毕业", "source": "resume"},
    {"period": "2020-2021", "kind": "gap", "summary": "资料空白期", "source": "inference"}
  ],
  "milestones": [
    {"milestone_kind": "turning_point", "summary": "第一份工作选了创业公司", "impact": "技能广但深不足", "source": "resume"}
  ],
  "relationships": [
    {"person": "母亲", "relation": "family", "closeness": "close", "influence": "希望其考编，形成稳定压力源", "source": "structured_form"}
  ],
  "aspirations": [
    {"horizon": "mid_term", "polarity": "want", "content": "2年内转行数据分析", "feasibility_note": "已有Python基础", "source": "structured_form"},
    {"horizon": "short_term", "polarity": "want_to_avoid", "content": "加班严重的岗位", "source": "structured_form"}
  ],

  "current_state": "…LLM 一段综合判断：此人当前处于什么人生阶段、核心张力是什么（阶段3生成）…",
  "conflicts": [{"field": "extraversion", "views": ["表单自评内向", "日记中组局频繁"], "resolution": "按自评为准,confidence=low"}],
  "source_coverage": {"structured_form": 0.5, "resume": 0.2, "diary": 0.3},
  "open_questions": ["缺少2020-2021资料", "未提及健康状态"]
}
```

> 分支层消费约定：`current_state` 是所有分支的公共起点；`timeline+milestones+LED_TO边` 提供因果素材；`aspirations(polarity)` 定义分支探索空间；`open_questions` 提示哪些分支方向证据不足。

---

## 六、API 契约

新蓝图 `app/api/profile.py`，注册于 `/api/profile`（`__init__.py` 加 3 行）。

| 端点 | 方法 | 请求 | 响应 |
|---|---|---|---|
| `/create` | POST | `{name?}` | `{project_id}` |
| `/structured-input` | POST | 2.1 节表单的 JSON | `{received_fields, normalized_text_preview}` |
| `/materials` | POST | multipart: 文件 + `material_type` + `time_range?`；或 JSON `{text, material_type}` | `{material_id, chunks}` |
| `/build` | POST | `{project_id}` | `{task_id}`（复用 TaskManager 轮询） |
| `/build/status/<task_id>` | GET | — | 与现有 graph 任务格式一致 |
| `/model/generate` | POST | `{project_id}` | `{task_id}`（三阶段合成任务） |
| `/model/generate/status/<task_id>` | GET | — | `{stage: "snapshot|narrative|synthesize", progress, message}` |
| `/model/<project_id>` | GET | `?version=` | personal_model.json |
| `/materials/append` | POST | 同 `/materials` | 触发增量 ingestion + 提示重新生成 |

---

## 七、实施阶段划分（评审通过后）

| 阶段 | 内容 | 交付物 | 状态 |
|---|---|---|---|
| P1 后端最小闭环 | person_ontology.py + profile.py 蓝图 + 预处理函数 + 复用建图 | 可用 curl 走完 表单→图谱 | ✅ 已完成 |
| P2 画像合成 | profile_synthesizer.py 三阶段 + personal_model 存储 + conflicts | 可用 curl 拿到完整个人模型 | 待实施 |
| P3 前端页面 | `/profile/create` 表单页 + `/profile/:id` 画像展示页（新路由，不动旧页面） | 完整可视体验 | 待实施 |
| P4 增量补料 | materials_manifest + append + 模型版本 diff | 长期使用的资料沉淀 | 部分（manifest 与去重已在 P1 落地） |

---

## 八、风险与边界

- **隐私**：日记等敏感内容将进入 Zep Cloud，私有化部署前需明示用户；本地开发建议用脱敏资料测试
- **Zep 限额**：实体 10 类型上限已用满，未来扩展需合并属性而非加类型
- **LLM 成本**：一次完整画像 ≈ 建图(资料量) + 3 次合成调用，远低于一次社会模拟
- **不承诺医疗/心理诊断**：emotional_patterns 仅作行为模式描述，产品文案需带免责声明
