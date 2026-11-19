RELEASES = [
{
    "version": "V0.7.7",
    "date": "2026-11-19",
    "title": {
        "zh-Hant": "全站介面一致性與考勤／假期／工資表／工作臺體驗整理",
        "zh-Hans": "全站界面一致性与考勤／假期／工资表／工作台体验整理",
        "en": "Cross-module UI consistency and usability improvements"
    },
    "features": {
        "zh-Hant": [
            "修正「考勤收集」檔案拖放區被全域檔案選擇器重複插入控制項與顯示「↑ *」的問題；將頁標題與「欠交名單」操作收齊於上傳區上方，並把左側「最近匯入批次」改為上下分行顯示完整批次標題。",
            "補全「假期管理」及「工傷管理」頁面（含側邊欄與全部彈窗）約百項繁體、簡體及英文三語翻譯，讓切換語言時整頁一致。",
            "為「工傷管理」員工卡片補上清晰卡片邊框與雙欄編輯彈窗、統一本頁年假／補休小數精度至 1 位，並套用可收合歷史面板（含預設展開的「復診／醫療開支歷史」與「假期變更歷史」）。",
            "補齊「資料設定與匯出」（工作日曆、項目、MPF 計劃、引用員工及清單）與工作臺到期狀態之繁／簡／英三語翻譯，並統一採用雙欄編輯彈窗與可收合離線日曆外框；員工詳情「證件與文件」文件總庫顯示具體目標分頁連結及「同檔多處關聯」標記。"
        ],
        "zh-Hans": [
            "修复“考勤收集”文件拖放区被全局文件选择器重复插入控件及显示“↑ *”的问题；将页标题与“欠交名单”操作收齐于上传区上方，并把左侧“最近导入批次”改为上下分行显示完整批次标题。",
            "补全“假期管理”及“工伤管理”页面（含侧边栏与全部弹窗）约百项繁体、简体及英文三语翻译，让切换语言时整页一致。",
            "为“工伤管理”员工卡片补上清晰卡片边框与双栏编辑弹窗、统一本页年假／补休小数精度至 1 位，并套用可折叠历史面板（含默认展开的“复诊／医疗开支历史”与“假期变更历史”）。",
            "补齐“资料设置与导出”（工作日历、项目、MPF 计划、引用员工及清单）与工作台到期状态之繁／简／英三语翻译，并统一采用双栏编辑弹窗与可折叠离线日历外框；员工详情“证件与文件”文件总库显示具体目标分页链接及“同文件多处关联”标记。"
        ],
        "en": [
            "Fixed the attendance PDF dropzone so the global file-picker enhancer no longer injects nested controls or appends an asterisk to the upload icon; moved the page title and Missing-attendance link above the dropzone, and stacked recent batch cards so batch titles display in full.",
            "Completed Traditional Chinese, Simplified Chinese, and English translations across Leave Management and Work Injury Management (including sidebar links and modal dialogs).",
            "Added visible borders to work-injury roster cards, standardized two-column modal layouts and 1-decimal leave balances, and aligned Leave & Work Injury history panels with the collapsible style.",
            "Completed trilingual translations and standardized dialogs and collapsible sections across Reference Data & Export (work calendar, projects, MPF schemes, options) and Workbench expiry countdowns; upgraded Employee Credentials & Files library links with target tab names and shared-file badges."
        ]
    },
    "improvements": {
        "zh-Hant": [
            "「每月工資表」總計卡片金額改為單行呈現不再於幣種後斷行、為 4 個底部進階面板套用一致收合標題與箭嘴；調整歷史與人員表欄寬及過濾器寬度，避免 1024px 窄屏擠壓與換行。",
            "「人事工作臺」證件到期日改為完整 `YYYY/MM/DD` 格式並為區塊標題補上展開／收合箭嘴；為假期總覽、每月工資表、工作臺及資料設定長表啟用表頭固定捲動。",
            "「員工詳情」在已有工資表快照而無月度考勤 PDF 時不再顯示矛盾的空白提示；收緊編輯個人資料彈窗尺寸、補上憑證按鈕懸浮提示並防止過長檔名撐闊詳情卡片；統一全站繁體介面用語為「匯出／工資表／離職結算／新增請假」（正式離職表英文名稱維持 `Final Payment`）。",
            "「員工檔案」按企業架構順序排列部門分組（管理層 → 工程管理部 → 成本合約部 → 船機設備部 → 財務部 → 人事行政部 → 地盤 → 印尼瑞沃 → 未填部門），並支援在「資料選項 → 所屬部門」自訂「顯示排序」。"
        ],
        "zh-Hans": [
            "“每月工资表”总计卡片金额改为单行呈现不再于币种后断行、为 4 个底部进阶面板套用一致折叠标题与箭头；调整历史与人员表栏宽及过滤器宽度，避免 1024px 窄屏挤压与换行。",
            "“人事工作台”证件到期日改为完整 `YYYY/MM/DD` 格式并为区块标题补上展开／折叠箭头；为假期总览、每月工资表、工作台及资料设置长表启用表头固定滚动。",
            "“员工详情”在已有工资表快照而无月度考勤 PDF 时不再显示矛盾的空白提示；收紧编辑个人资料弹窗尺寸、补上凭证按钮悬浮提示并防止过长文件名撑宽详情卡片；统一全站简体界面用语为“工资表／离职结算／新增请假”（正式离职表英文名称维持 `Final Payment`）。",
            "“员工档案”按企业架构顺序排列部门分组（管理层 → 工程管理部 → 成本合约部 → 船机设备部 → 财务部 → 人事行政部 → 地盘 → 印尼瑞沃 → 未填部门），并支持在“资料选项 → 所属部门”自定义“显示排序”。"
        ],
        "en": [
            "Kept Payroll KPI currency amounts on single lines, unified the four lower Payroll disclosures with standard collapsible headers and chevrons, tuned table widths for 1024px viewports, and enabled sticky table headers across Leave overview, Payroll, Workbench and Reference tables.",
            "Formatted HR Workbench certificate expiry dates as `YYYY/MM/DD` with full-width toggle headers and chevrons, framed the Payroll summary strip, and adjusted wrapping at 1024px.",
            "Updated Employee Profile Tab 5 so saved payroll snapshots without monthly attendance PDFs show an accurate hint instead of an empty-state contradiction, compacted the personal-details modal, constrained long evidence links, and aligned Chinese UI terminology across templates and messages.",
            "Ordered Employee Directory departments by corporate hierarchy (Management first through site/overseas operations, Unassigned last) with optional custom Display order overrides in Reference Data."
        ]
    },
    "limitations": {
        "zh-Hant": [],
        "zh-Hans": [],
        "en": []
    }
},
{
    "version": "V0.7.6",
    "date": "2026-11-19",
    "title": {
        "zh-Hant": "員工詳情頁籤「變更歷史」風格統一",
        "zh-Hans": "员工详情页签“变更历史”风格统一",
        "en": "Unified collapsible history panels across employee tabs"
    },
    "features": {
        "zh-Hant": [
            "個人資料、任職與薪酬、證件與文件、假期與工傷及考勤與出糧五個頁籤改為一致的頁面結構：上方集中展示當前資料卡片，最下方保留單一預設展開、可點擊收合的紀錄／變更歷史外框。",
            "「任職與薪酬」將原「任職狀態變更歷史」合併入底部單一「變更歷史」，不再攔腰打斷卡片區；「證件與文件」歷史由頁面中段移至最底並預設展開。"
        ],
        "zh-Hans": [
            "个人资料、任职与薪酬、证件与文件、假期与工伤及考勤与出粮五个页签改为一致的页面结构：上方集中展示当前资料卡片，最下方保留单一默认展开、可点击折叠的记录／变更历史外框。",
            "“任职与薪酬”将原“任职状态变更历史”合并入底部单一“变更历史”，不再拦腰打断卡片区；“证件与文件”历史由页面中段移至最底并默认展开。"
        ],
        "en": [
            "All five employee profile tabs share a consistent layout: current status cards on top with a single default-open collapsible history panel at the bottom.",
            "Employment status history is merged into the unified Change history panel at the bottom of the Employment & Pay tab, and credential history moves to the bottom of Credentials & Files and opens by default."
        ]
    },
    "improvements": {
        "zh-Hant": [
            "統一個人資料、任職與薪酬、證件與文件三頁籤歷史標題為「變更歷史」並顯示筆數；假期與工傷下方改為同款可收合「假期與工傷紀錄」面板。"
        ],
        "zh-Hans": [
            "统一个人资料、任职与薪酬、证件与文件三页签历史标题为“变更历史”并显示笔数；假期与工伤下方改为同款可折叠“假期与工伤记录”面板。"
        ],
        "en": [
            "Standardized Change history headers with item counts across Personal, Employment & Pay, and Credentials & Files, and wrapped Leave & Injury records and Historical adjustments in the same collapsible panel."
        ]
    },
    "limitations": {
        "zh-Hant": [],
        "zh-Hans": [],
        "en": []
    }
},
{
    "version": "V0.7.5",
    "date": "2026-11-19",
    "title": {
        "zh-Hant": "員工檔案與詳情介面整理",
        "zh-Hans": "员工档案与详情界面整理",
        "en": "Employee directory and profile UI cleanup"
    },
    "features": {
        "zh-Hant": [
            "員工詳情頁頂部缺件標籤可直接點擊跳轉至對應補資料頁面或表單，並一律提供返回「員工檔案」連結；變更歷史改以彈窗補充任職與薪酬憑證，修正欄位重疊與拉高表格的問題。"
        ],
        "zh-Hans": [
            "员工详情页顶部缺件标签可直接点击跳转至对应补资料页面或表单，并统一提供返回“员工档案”链接；变更历史改以弹窗补充任职与薪酬凭证，修复字段重叠与表格过高的问题。"
        ],
        "en": [
            "Missing-data badges in the employee header link directly to the relevant upload page or editor, a back link to Employee Files always renders, and assignment/salary evidence uploads use modal dialogs without overflowing history table columns."
        ]
    },
    "improvements": {
        "zh-Hant": [
            "修正 1024px 寬度下頂部導覽列橫向溢出、名冊「更多篩選」頂線偏移與個人資料頁重複按鈕及銀行帳號斷行；收斂已有基本任職及薪酬紀錄員工的入職補齊橫條、空文件分類篩選、日工不適用補貼卡及管理員刪除區。",
            "統一假期與工傷、考勤與工資紀錄頁籤的按鈕動詞與空態文字，讓 3 張假期餘額卡滿版排列，並為負數工資表快照加上醒目警示標籤。"
        ],
        "zh-Hans": [
            "修复 1024px 宽度下顶部导航栏横向溢出、名册“更多筛选”顶线偏移以及个人资料页重复按钮和银行账号换行；收敛已有基本任职及薪酬记录员工的入职补齐横条、空文件分类筛选、日工不适用补贴卡及管理员删除区。",
            "统一假期与工伤、考勤与工资记录页签的按钮动词与空态文字，让 3 张假期余额卡满版排列，并为负数工资表快照加上醒目警示标签。"
        ],
        "en": [
            "Fitted the primary navigation bar cleanly at 1024px, aligned directory filter controls, de-duplicated personal edit buttons, kept masked bank account numbers intact on full-width cards, and collapsed onboarding prompts, empty filter pills, inapplicable daily-worker allowances and the admin danger zone.",
            "Unified leave and payroll action labels and empty states, expanded the 3-card leave balance strip across the full width, and highlighted negative payroll snapshots with a warning badge."
        ]
    },
    "limitations": {
        "zh-Hant": [],
        "zh-Hans": [],
        "en": []
    }
},
{
    "version": "V0.7.4",
    "date": "2026-11-19",
    "title": {
        "zh-Hant": "防誤換表、月份／公司篩選及管理員歷史核對",
        "zh-Hans": "防误换表、月份／公司筛选及管理员历史核对",
        "en": "Safer replacement shortcuts, scoped lists and historical review"
    },
    "features": {
        "zh-Hant": [
            "本月已收考勤表時，按 Ctrl + Enter 或 Enter 不會誤按「替換原表」；同時操作同一份考勤表時不會靜默覆蓋他人剛保存的數字。",
            "管理員可在「歷史核對」唯讀查閱曾替換的考勤 PDF、日工工傷核實月收入對照，以及未綁定續證的舊證提醒。"
        ],
        "zh-Hans": [
            "本月已收考勤表时，按 Ctrl + Enter 或 Enter 不会误按“替换原表”；同时操作同一份考勤表时不会静默覆盖他人刚保存的数字。",
            "管理员可在“历史核对”只读查阅曾替换的考勤 PDF、日工工伤核实月收入对照，以及未绑定续证的旧证提醒。"
        ],
        "en": [
            "Ctrl + Enter and Enter stop before replacing an existing attendance sheet, and concurrent saves to the same attendance item or summary reject stale edits.",
            "Admins have a read-only Historical Review page checking replaced attendance PDFs, daily-worker injury verified earnings and unlinked credential renewals."
        ]
    },
    "improvements": {
        "zh-Hant": [
            "考勤「繼續錄入」僅處理所選月份；其他月份尚有待錄批次時另行顯示連結。",
            "「當月已保存工資表」嚴格依選定的發薪單位與薪酬組別過濾，時間欄名改為香港時間。"
        ],
        "zh-Hans": [
            "考勤“继续录入”仅处理所选月份；其他月份尚有待录批次时另行显示链接。",
            "“当月已保存工资表”严格按选定的发薪单位与薪酬组别筛选，时间列名改为香港时间。"
        ],
        "en": [
            "Continue entry stays within the selected attendance month and links separately to unfinished batches from other months.",
            "Saved monthly payroll runs follow the selected paying entity and payroll group strictly, and label saved timestamps as HKT."
        ]
    },
    "limitations": {
        "zh-Hant": [],
        "zh-Hans": [],
        "en": []
    }
},
{
    "version": "V0.7.3",
    "date": "2026-11-18",
    "title": {
        "zh-Hant": "考勤換表、續證與工傷登記",
        "zh-Hans": "考勤换表、续证与工伤登记",
        "en": "Attendance replacements, renewals and injury entry"
    },
    "features": {
        "zh-Hant": [
            "本月已收表時請改選員工或按「替換原表」，舊批次保留原 PDF。",
            "舊證按「續證」，新證生效後停止舊提醒。半天假只需一個日期，工傷按意外當日的薪率供核對；日工須填已核實月收入。"
        ],
        "zh-Hans": [
            "本月已收表时请改选员工或点击“替换原表”，旧批次保留原 PDF。",
            "从旧证点击“续证”，新证生效后停止旧提醒。半天假只需一个日期，工伤按意外当日的薪率供核对；日工须填已核实月收入。"
        ],
        "en": [
            "Choose a different employee or explicitly replace a received sheet. The original PDF remains in the batch.",
            "Renew a credential from its card. The earlier reminder ends when the renewal takes effect. Half-day leave uses one date. Enter verified monthly earnings for daily-paid injured staff."
        ]
    },
    "improvements": {
        "zh-Hant": [
            "每月工資表可查看未分配發薪單位的人員。批次時間採香港時間。"
        ],
        "zh-Hans": [
            "每月工资表可查看未分配发薪单位的人员。批次时间采用香港时间。"
        ],
        "en": [
            "Monthly payroll links to employees without a paying entity. Batch timestamps use Hong Kong time."
        ]
    },
    "limitations": {
        "zh-Hant": [],
        "zh-Hans": [],
        "en": []
    }
},
    {
        "version": "V0.7.2", "date": "2026-11-18",
        "title": {"zh-Hant": "出糧待核對與員工名冊", "zh-Hans": "发薪待核对与员工名册", "en": "Payroll review and staff directory"},
        "features": {
            "zh-Hant": ["從出糧待核對補薪酬、銀行及發薪單位，或打開負數工資的當月計算明細。", "按部門或職位瀏覽員工姓名及編號卡片。"],
            "zh-Hans": ["从发薪待核对补薪酬、银行及发薪单位，或打开负数工资的当月计算明细。", "按部门或职位浏览员工姓名及编号卡片。"],
            "en": ["Resolve missing pay rates, bank details and paying entities or open the monthly breakdown for negative net pay.", "Browse employee cards by department or position."],
        },
        "improvements": {
            "zh-Hant": ["個人檔案分為五頁。證件、文件和合約集中在一起，轉正及離職在任職與薪酬辦理。", "名冊預設列出在職員工，點姓名卡片即可開啟檔案。可按姓名或編號搜尋，亦可切換至離職名單。", "從出糧待核對補好薪酬、銀行或發薪單位後，會返回原月份，並保留公司、組別和搜尋條件。"],
            "zh-Hans": ["个人档案分为五页。证件、文件和合约集中在一起，转正及离职在任职与薪酬办理。", "名册默认列出在职员工，点击姓名卡片即可打开档案。可按姓名或编号搜索，也可切换至离职名单。", "从发薪待核对补好薪酬、银行或发薪单位后，会返回原月份，并保留公司、组别和搜索条件。"],
            "en": ["Five profile tabs bring credentials and files together and keep employment status with employment terms.", "The directory opens with cards for current staff. Select a card, search by name or staff number, or switch to former staff.", "After saving pay rates, bank details or a paying entity from payroll review, you return to the same month, company, group and search."],
        },
        "limitations": {"zh-Hant": [], "zh-Hans": [], "en": []},
    },
{
  "version": "V0.7.1",
  "date": "2026-11-18",
  "title": {
    "zh-Hant": "人事工作臺、考勤交接與每月出糧",
    "zh-Hans": "人事工作台、考勤交接与每月发薪",
    "en": "HR workbench, attendance handover and monthly payroll"
  },
  "features": {
    "zh-Hant": [
      "登入後在人事工作臺查看證件到期、休假、工傷及本月出糧進度。點員工那一行可開啟相應紀錄。",
      "在「考勤錄入」一次上傳整批 PDF，先看原表，再選員工。下一位同事按「繼續錄入」，便可從第一份待錄 PDF 接手。欠交考勤表的員工另有名單。",
      "「假期與工傷」集中顯示今日在休、未來七日休假、工傷、年假和補休結餘。在員工那一行可直接登記假期。"
    ],
    "zh-Hans": [
      "登录后在人事工作台查看证件到期、休假、工伤及本月发薪进度。点击员工所在行可打开相应记录。",
      "在「考勤录入」一次上传整批 PDF，先看原表，再选员工。下一位同事点击「继续录入」，即可从第一份待录 PDF 接手。欠交考勤表的员工另有名单。",
      "「假期与工伤」集中显示今日在休、未来七日休假、工伤、年假和补休结余。在员工所在行可直接登记假期。"
    ],
    "en": [
      "The HR workbench shows expiring documents, leave, injuries and monthly payroll progress. Open an employee’s record from their row.",
      "Upload a batch of attendance PDFs, review each sheet and select its employee. Continue entry opens the first pending PDF for the next operator. A separate roster lists staff who still owe a sheet.",
      "Leave and injury shows who is away today or in the coming week, injury cases, annual leave and time-off balances. Register leave from the employee’s row."
    ]
  },
  "improvements": {
    "zh-Hant": [
      "員工檔案的證件卡直接顯示到期日、附件和更正入口，舊資料可在變更歷史查看。",
      "工資表集中顯示月份、發薪單位、可出糧人數及匯出按鈕。從待核對員工開啟考勤，保存後會回到原來的工資表範圍。只補交病假憑證會保留既有核對狀態。",
      "工作臺與工資表採用同一份可出糧名單。整月工傷及月中入職按適用期間處理，已保存的工資表可重新下載。"
    ],
    "zh-Hans": [
      "员工档案的证件卡直接显示到期日、附件和更正入口，旧资料可在变更历史查看。",
      "工资表集中显示月份、发薪单位、可发薪人数及导出按钮。从待核对员工打开考勤，保存后会回到原来的工资表范围。只补交病假凭证会保留已有核对状态。",
      "工作台与工资表采用同一份可发薪名单。整月工伤及月中入职按适用期间处理，已保存的工资表可重新下载。"
    ],
    "en": [
      "Credential cards show expiry dates, attachments and an edit action. Earlier entries remain available in the change history.",
      "Payroll brings the month, paying entity, eligible headcount and export together. Review attendance from a pending employee’s row and return to the same payroll scope after saving. Supplying sick leave evidence alone preserves the existing review status.",
      "The workbench and payroll use the same eligible roster. Full-month injury leave and mid-month hires follow their applicable dates. Previously saved payroll tables can be downloaded again."
    ]
  },
  "limitations": {
    "zh-Hant": ["每份考勤 PDF 由同事核對及選定所屬員工。正式匯出工資表時須選擇發薪單位。"],
    "zh-Hans": ["每份考勤 PDF 由同事核对并选定所属员工。正式导出工资表时须选择发薪单位。"],
    "en": ["An operator reviews each PDF and selects its employee. Select a paying entity before exporting payroll."]
  }
},
{
  "version": "V0.7.0",
  "date": "2026-11-18",
  "title": {
    "zh-Hant": "在考勤錄入更正過往出勤及 OT",
    "zh-Hans": "在考勤录入更正过往出勤及 OT",
    "en": "Correct prior attendance in the current payroll month"
  },
  "features": {
    "zh-Hant": [
      "在員工本期的考勤 PDF 詳情按「更正過往考勤」，選原月份和工作日，逐項填寫要補回或扣回的出勤及 OT。",
      "一筆更正可用同一個按鈕選取多份 PDF 或圖片憑證，沒有附件也可保存。"
    ],
    "zh-Hans": [
      "在员工本期的考勤 PDF 详情点击「更正过往考勤」，选择原月份和工作日，逐项填写要补回或扣回的出勤及 OT。",
      "一笔更正可用同一个按钮选择多份 PDF 或图片凭证，没有附件也可保存。"
    ],
    "en": [
      "From the employee's current attendance PDF, choose Correct Prior Attendance, then enter the work dates and the attendance or overtime to add or deduct.",
      "Use one button to attach multiple supporting PDFs or images. Attachments are optional."
    ]
  },
  "improvements": {
    "zh-Hant": [
      "按原工作日的薪酬規則自動計算差額，計入本期 Payroll。固定月薪的普通出勤只記日數；OT 按原工作日規則計算。",
      "日工 Excel 的 AG 欄、月工及 OFFICE 的 AH 欄合併到 Other Payment，註解列明逐日差額。原月考勤和本期 Payroll 都可查看紀錄及憑證。",
      "移除手填工資調整金額的入口，保留既有紀錄和憑證。"
    ],
    "zh-Hans": [
      "按原工作日的薪酬规则自动计算差额，计入本期 Payroll。固定月薪的普通出勤只记天数；OT 按原工作日规则计算。",
      "日工 Excel 的 AG 列、月工及 OFFICE 的 AH 列合并到 Other Payment，批注列明逐日差额。原月考勤和本期 Payroll 都可查看记录及凭证。",
      "移除手填工资调整金额的入口，保留已有记录和凭证。"
    ],
    "en": [
      "The work date's pay rules determine the difference, which is carried into the current payroll. Ordinary attendance corrections for fixed monthly pay record days only; overtime follows the work date's rules.",
      "Excel includes the net amount in Other Payment (AG for daily workers, AH for monthly and OFFICE staff), with dated comments. View the record and attachments from original attendance or current payroll.",
      "The manual wage adjustment entry has been removed. Existing records and supporting files remain available."
    ]
  },
  "limitations": {
    "zh-Hant": [
      "更正上月 21 日至月底的考勤時，須核對該筆是否已計入本期的「上月尾段實際」，避免重複計薪。"
    ],
    "zh-Hans": [
      "更正上月 21 日至月底的考勤时，须核对该笔是否已计入本期的「上月尾段实际」，避免重复计薪。"
    ],
    "en": [
      "For dates from the 21st through the end of the previous month, check whether the correction is already included in this month's prior-period actuals to avoid double counting."
    ]
  }
},
{
  "version": "V0.6.0",
  "date": "2026-11-04",
  "title": {
    "zh-Hant": "三人工作流程整合與計薪修正",
    "zh-Hans": "三人工作流程整合与计薪修正",
    "en": "Small-team workflow and payroll corrections"
  },
  "features": {
    "zh-Hant": [
      "月份工作台、一次入職設定、逐檔考勤上傳及空白薪酬紀錄批量預填。",
      "跨薪酬生效日期分段計算；離職月份共用調整入口。",
      "離線依賴安裝及工作日曆 CSV。",
      "內置離線 PDF 預覽，支援翻頁、縮放、旋轉及原檔下載；改善考勤與假期畫面。"
    ],
    "zh-Hans": [
      "月份工作台、一次入职设置、逐份考勤上传及空白薪酬记录批量预填。",
      "按薪酬生效日期分段计算；离职月份共用调整入口。",
      "离线依赖安装及工作日历 CSV。",
      "内置离线 PDF 预览，支持翻页、缩放、旋转及原文件下载；改善考勤与假期页面。"
    ],
    "en": [
      "Monthly context, one-save initial setup, per-file attendance queue and blank salary-record prefill.",
      "Date-specific attendance rates and shared departure adjustment editor.",
      "Offline dependency installation and work-calendar CSV.",
      "Bundled offline PDF preview with pages, zoom, rotation and original download; refined attendance and leave layouts."
    ]
  },
  "improvements": {
    "zh-Hant": [
      "合約草稿獨立保存，按生效日帶入薪酬，保留零值且不改正式條款。",
      "新快照保存歷史身份及項目名稱；就緒狀態與可匯出範圍一致。",
      "考勤錯誤保留輸入；員工、假期、工傷及 Payroll 先呈現待辦。"
    ],
    "zh-Hans": [
      "合同草稿独立保存，按生效日带入薪酬，保留零值且不改正式条款。",
      "新快照保存历史身份及项目名称；就绪状态与可导出范围一致。",
      "考勤错误保留输入；员工、假期、工伤及 Payroll 优先显示待办。"
    ],
    "en": [
      "Unique dated contract drafts preserve zero terms and formal employment facts.",
      "New snapshots freeze identifying facts; readiness and export scope agree.",
      "Retain failed form input and prioritize operational exceptions."
    ]
  },
  "limitations": {
    "zh-Hant": [
      "舊快照未保存的身份欄位無法還原；舊跨費率實際考勤須按原件補分段。",
      "部署、程序重啟及現場驗證另行記錄，不由此版本列表代表。"
    ],
    "zh-Hans": [
      "旧快照未保存的身份字段无法还原；旧跨费率实际考勤须按原件补分段。",
      "部署、程序重启及现场验证另行记录。"
    ],
    "en": [
      "Identity facts missing from old snapshots cannot be reconstructed; legacy mixed-rate actual totals need dated allocations.",
      "Deployment, restart and live verification are reported separately."
    ]
  }
},
{
 'version': 'V0.5.10', 'date': '2026-10-09',
 'title': {'zh-Hant': '修正入職日期時確認年假額度', 'zh-Hans': '修正入职日期时确认年假额度', 'en': 'Confirm entitlement when correcting start dates'},
 'features': {
  'zh-Hant': ['修改入職日期時，保存前列出原額度與新計算值，選擇重算或保留本年度額度。'],
  'zh-Hans': ['修改入职日期时，保存前列出原额度与新计算值，选择重算或保留本年度额度。'],
  'en': ['Before saving a corrected start date, compare entitlement and choose whether to recalculate or keep this year.']},
 'improvements': {
  'zh-Hant': ['年假設定與 Staff Record 採用相同確認流程；保留不延續到往後年度，取消不保存。未到入職日的員工也可開啟個人年假頁。'],
  'zh-Hans': ['年假设置与 Staff Record 采用相同确认流程；保留不延续到往后年度，取消不保存。未到入职日的员工也可打开个人年假页。'],
  'en': ['Confirm leave setup and Staff Record corrections consistently. Future hire dates remain accessible in individual leave pages.']},
 'limitations': {'zh-Hant': [], 'zh-Hans': [], 'en': []}
},
{
 'version': 'V0.5.9', 'date': '2026-10-09',
 'title': {'zh-Hant': '年假保存衝突比對修正', 'zh-Hans': '年假保存冲突比对修正', 'en': 'Annual leave save revision correction'},
 'features': {'zh-Hant': [], 'zh-Hans': [], 'en': []},
 'improvements': {
  'zh-Hant': ['年假資料版本比對忽略帳戶讀取順序及數字顯示精度，避免未變更資料被誤判為過期表單。', '真正資料衝突時明確提示刷新頁面；保存成功沿用關閉視窗並更新額度的流程。', '補填舊年假後，本年度修正清單仍保留該年度最近修正；人工額度調整列出保存前後額度。'],
  'zh-Hans': ['年假资料版本比对忽略账户读取顺序及数字显示精度，避免未变更资料被误判为过期表单。', '真正资料冲突时明确提示刷新页面；保存成功沿用关闭窗口并更新额度的流程。'],
  'en': ['Compare leave revisions independently of relationship row order and numeric display scale.', 'Refresh the page for real conflicts; successful saves close the dialog and refresh balances.']},
 'limitations': {'zh-Hant': ['保留真正資料變更的衝突保護；新版部署後需重啟並刷新舊頁面。'], 'zh-Hans': ['保留真正资料变更的冲突保护；新版部署后需重启并刷新旧页面。'], 'en': ['Real changes still reject stale forms. Restart after deployment and refresh existing pages.']}
},
{
 'version': 'V0.5.8', 'date': '2026-10-09',
 'title': {'zh-Hant': '曆年預支年假與離職追扣', 'zh-Hans': '历年预支年假与离职追扣', 'en': 'Calendar-year advance leave and departure deductions'},
 'features': {
  'zh-Hant': ['HR 確認入職日期及初始年假後，保存本年度折算額度；首年取最近半天，往後依公司級距自動計算。', '新增本年度核對及修正清單，列出計算依據、待補項目及最近保存前後額度。'],
  'zh-Hans': ['HR 确认入职日期及初始年假后，保存本年度折算额度；首年取最近半天，往后依公司级距自动计算。', '新增本年度核对及修正清单，列出计算依据、待补项目及最近保存前后额度。'],
  'en': ['Confirm start date and initial leave to save current-year entitlement, rounded to the nearest half day for the hire year.', 'Review missing bases and saved before/after entitlement changes in one list.']},
 'improvements': {
  'zh-Hant': ['跨年首次使用時補建當年帳戶，保留歷史帳戶、舊年假空卡及逐年人工額度。', '離職視窗預覽完整精度折算、超用及追扣；缺有效日薪時阻止結算匯出。簽署合約可明確修正初始年假。'],
  'zh-Hans': ['跨年首次使用时补建当年账户，保留历史账户、旧年假空卡及逐年人工额度。', '离职窗口预览完整精度折算、超用及追扣；缺有效日薪时阻止结算导出。签署合同可明确修正初始年假。'],
  'en': ['Persist the current-year account on first use after rollover while preserving historical balances and manual overrides.', 'Preview departure earning and excess deductions; block export without a valid daily rate. Apply reviewed signed-contract corrections explicitly.']},
 'limitations': {
  'zh-Hant': ['既有員工須 HR 確認計算依據，不批量猜測或覆蓋；2023 及以前總額由 HR 核實填寫。', '只保存當年，不補建歷史年度；影響已匯出 Payroll 時須核對並重新匯出。'],
  'zh-Hans': ['既有员工须 HR 确认计算依据，不批量猜测或覆盖；2023 及以前总额由 HR 核实填写。', '只保存当年，不补建历史年度；影响已导出 Payroll 时须核对并重新导出。'],
  'en': ['Existing employees require HR-confirmed bases; legacy totals remain manual. No speculative bulk overwrite.', 'Only the current year is saved. Review and re-export affected Payroll snapshots.']}
},
{'version': 'V0.5.7',
 'date': '2026-09-24',
 'title': {'zh-Hant': '測試修正與資料保護', 'zh-Hans': '测试修正与资料保护', 'en': 'Review fixes and data protection'},
 'features': {'zh-Hant': ['負實發及考勤待重核禁止匯出，提示員工姓名；HR 直接保存匯率，摘要折合 HKD。'], 'zh-Hans': ['负实发及考勤待复核禁止导出，提示员工姓名；HR 直接保存汇率，摘要折合 HKD。'], 'en': ['Block negative-net and stale-attendance exports with employee names; HR-entered rates convert display totals to HKD.']},
 'improvements': {'zh-Hant': ['看板、每月及離職 Payroll 摘要按幣種分開，項目小計不混加幣種；列明工傷醫療報銷與實發的關係。',
                              '阻止無效薪酬金額與過期個人資料表單覆蓋；員工 Excel 匯出把公式樣式的文字保留為文字。',
                              '重設密碼即使既有登入失效；PDF 檢查可讀頁面結構，附件頁提示遺失及空檔。',
                              '減少員工工作台重複查詢，修正窄螢幕橫向溢出及無效月份／年份錯誤。'],
                  'zh-Hans': ['看板、每月及离职 Payroll 摘要按币种分开，项目小计不混加币种；列明工伤医疗报销与实发的关系。',
                              '阻止无效薪酬金额与过期个人资料表单覆盖；员工 Excel 导出把公式样式的文字保留为文字。',
                              '重设密码即使既有登录失效；PDF 检查可读页面结构，附件页提示遗失及空文件。',
                              '减少员工工作台重复查询，修正窄屏横向溢出及无效月份／年份错误。'],
                  'en': ['Separate dashboard, monthly and final Payroll totals by currency; explain medical '
                         'reimbursement in net pay.',
                         'Reject invalid salary amounts and stale profile submissions; keep formula-like employee '
                         'export data as text.',
                         'Password resets invalidate existing sessions; validate PDF page structure and flag '
                         'missing or empty attachments.',
                         'Batch workbench queries, constrain narrow-screen content and reject invalid calendar '
                         'parameters.']},
 'limitations': {'zh-Hant': ['匯率僅換算畫面摘要，不更改已保存 Payroll、員工原幣金額或附件。', '部署後現有登入須重新登入；附件存在／大小檢查不代表內容及簽署已核實。'],
                 'zh-Hans': ['汇率仅换算画面摘要，不更改已保存 Payroll、员工原币金额或附件。', '部署后现有登录须重新登录；附件存在／大小检查不代表内容及签署已核实。'],
                 'en': ['Rates convert display totals only, without rewriting saved Payroll, original employee amounts or '
                        'source attachments.',
                        'Deployment requires users to sign in again. File availability checks do not verify '
                        'document content or signatures.']}},
{
    "version": "V0.5.6", "date": "2026-09-16",
    "title": {"zh-Hant":"月薪項目日期分攤與 MPF 豁免", "zh-Hans":"月薪项目日期分摊与 MPF 豁免", "en":"Monthly project dates and MPF exemptions"},
    "features": {
        "zh-Hant":["一份考勤 PDF 可一次錄入多個項目；月薪只將調配期間的正常工作日份額轉往其他項目，休息日及適用有薪假日留在原項目。", "星期六依 5／5.5／6 天制分別轉移 0／半天／一天。底薪及未指定項目的固定補貼按同一份額分攤；OT、E-CALL、額外工作及上月補差保留各自考勤項目。"],
        "zh-Hans":["一份考勤 PDF 可一次录入多个项目；月薪只将调配期间的正常工作日份额转往其他项目，休息日及适用有薪假日留在原项目。", "星期六依 5／5.5／6 天制分别转移 0／半天／一天。底薪及未指定项目的固定补贴按同一份额分摊；OT、E-CALL、额外工作及上月补差保留各自考勤项目。"],
        "en":["Enter multiple projects from one PDF. Monthly transfers apply only to scheduled workday shares; rest days and applicable paid holidays stay with the home project.", "Saturday transfers 0, half or one day under 5, 5.5 or 6-day schedules. Base pay and unassigned fixed allowances use these shares; attendance extras and prior-tail pay retain their own projects."]
    },
    "improvements": {
        "zh-Hant":["MPF 豁免記錄可不選計劃；無計劃的豁免員工不阻擋供款表匯出，有計劃者仍列於所屬報表。", "修正員工檔案將已收考勤誤顯示為已撤回。", "跨項目彈窗加寬，只展開需要的時段；日期可只填調配期間，重疊或跨月份時阻止保存。分行總薪金不變，MPF 不重複扣除。"],
        "zh-Hans":["MPF 豁免记录可不选计划；无计划的豁免员工不阻挡供款表导出，有计划者仍列于所属报表。", "修正员工档案将已收考勤误显示为已撤回。", "跨项目弹窗加宽，只展开需要的时段；日期可只填调配期间，重叠或跨月份时阻止保存。分行总薪金不变，MPF 不重复扣除。"],
        "en":["Exempt MPF records may omit a scheme without blocking other scheme reports.", "Correct received attendance incorrectly labelled as withdrawn in employee profiles.", "Widen the project editor and expand only needed periods. Partial transfers are allowed, overlapping or out-of-month dates are rejected. Total pay is preserved and MPF deducted only once."]
    },
    "limitations": {
        "zh-Hant":["只在 HR 明確勾選並保存後生效；舊全曆日分攤須明確確認改用工作日規則。不批量更改既有員工或已保存 Payroll 快照，需核對後重新匯出。", "日工及按出勤日數計薪仍按考勤項目處理；離職 Payroll 不使用此每月分攤設定。"],
        "zh-Hans":["只在 HR 明确勾选并保存后生效；旧全历日分摊须明确确认改用工作日规则。不批量更改既有员工或已保存 Payroll 快照，需核对后重新导出。", "日工及按出勤日数计薪仍按考勤项目处理；离职 Payroll 不使用此每月分摊设置。"],
        "en":["Opt-in only. Legacy calendar allocation requires explicit conversion. No bulk employee or saved Payroll rewrites; review and re-export.", "Daily and attendance-based pay keep attendance projects. Departure Payroll does not use this monthly allocation."]
    }
},
{
    "version": "V0.5.5", "date": "2026-09-10",
    "title": {"zh-Hant":"獨立薪酬紀錄與年度匯總", "zh-Hans":"独立薪酬记录与年度汇总", "en":"Independent salary records and annual summaries"},
    "features": {
        "zh-Hant":["新增薪酬紀錄：由 2026 年 4 月起，按員工、月份及發薪單位手動填寫應發工資、員工 MPF 實際扣款及實發金額。", "年度匯總按 4 月至翌年 3 月展示，包含離職員工，分開發薪單位及幣種，支援匯出年度匯總與每月明細。", "員工檔案的考勤與 Payroll 可唯讀查閱薪酬紀錄，新增、更正及撤回集中於同一入口。"],
        "zh-Hans":["新增薪酬记录：由 2026 年 4 月起，按员工、月份及发薪单位手动填写应发工资、员工 MPF 实际扣款及实发金额。", "年度汇总按 4 月至翌年 3 月展示，包含离职员工，分开发薪单位及币种，支持导出年度汇总与每月明细。", "员工档案的考勤与 Payroll 可只读查阅薪酬记录，新增、更正及撤回集中于同一入口。"],
        "en":["Record gross pay, actual employee MPF deductions and net payment by employee, month and entity from April 2026.", "April–March summaries include departed employees, separate entities and currencies, and export annual totals plus monthly detail.", "Employee profiles show read-only salary history linked to one central editor."]
    },
    "improvements": {
        "zh-Hant":["員工 MPF 賬號改為可不填，新增、更正、資料完整度及 MPF 匯出同步取消必填限制；不改供款計算。", "幣種改用資料設定下拉選項；金額統一千分位與兩位小數。", "MPF 補扣以實際扣薪月份記錄；實發與應發減 MPF 不一致可備註後保存，空白不視為零。", "可明確帶入相符已保存 Payroll 作預填，但需人工核對保存；更正及撤回保留香港時間審計與歷史憑證。", "多人修改或過期提交阻止覆蓋；整批驗證成功才保存，錯誤時保留畫面輸入及所選附件。"],
        "zh-Hans":["员工 MPF 账号改为可不填，新增、更正、资料完整度及 MPF 导出同步取消必填限制；不改供款计算。", "币种改用资料设置下拉选项；金额统一千分位与两位小数。", "MPF 补扣以实际扣薪月份记录；实发与应发减 MPF 不一致可备注后保存，空白不视为零。", "可明确带入相符已保存 Payroll 作预填，但需人工核对保存；更正及撤回保留香港时间审计与历史凭证。", "多人修改或过期提交阻止覆盖；整批验证成功才保存，错误时保留页面输入及所选附件。"],
        "en":["Employee MPF member accounts are optional for entry, correction, completeness and export; contribution calculations are unchanged.", "Use Data Settings currencies and display amounts with thousands separators and two decimals.", "Catch-up MPF belongs to the actual deduction month; manual net overrides are allowed, and blank is not zero.", "Explicitly load a matching saved Payroll snapshot for review; corrections, withdrawals and evidence retain audit history in Hong Kong time.", "Stale submissions cannot overwrite newer changes. Validate the entire batch before saving and retain browser inputs on validation errors."]
    },
    "limitations": {
        "zh-Hant":["完全獨立於現有 Payroll、MPF 供款表及年假／離職補薪計算；不會自動回寫或隨重新計算改動。", "年度匯總只供核對，不等於正式報稅表；未錄入月份按任職資料核對，未來月份不列缺漏。"],
        "zh-Hans":["完全独立于现有 Payroll、MPF 供款表及年假／离职补薪计算；不会自动回写或随重新计算改动。", "年度汇总仅供核对，不等于正式报税表；未录入月份按任职资料核对，未来月份不列缺漏。"],
        "en":["No write-back to Payroll, MPF returns or leave/final-payment averages; saved records do not change on recalculation.", "This is a reconciliation register, not a statutory tax return. Employment data determines missing months; future months are excluded."]
    }
},
{
    "version": "V0.5.4", "date": "2026-09-09",
    "title": {"zh-Hant": "假期差異一鍵核對與 Payroll 同步更新", "zh-Hans": "假期差异一键核对与 Payroll 同步更新", "en": "Batch leave review and Payroll recalculation"},
    "features": {
        "zh-Hant": ["任職與薪酬提示該員工待核對假期，直接進入已篩選的差異清單。", "HR 勾選後一次更新假期日數及扣帳，保留原日期、時段、憑證與備註；無需逐筆開啟更正。", "核對階段確認更新會同步重新計算相關已有 Payroll 月份及離職年假補薪，保留舊快照和前後審計。"],
        "zh-Hans": ["任职与薪酬提示该员工待核对假期，直接进入已筛选的差异清单。", "HR 勾选后一次更新假期日数及扣账，保留原日期、时段、凭证与备注；无需逐笔打开更正。", "核对阶段确认更新会同步重新计算相关已有 Payroll 月份及离职年假补薪，保留旧快照和前后审计。"],
        "en": ["Employment & Salary links directly to the employee's leave differences.", "Update selected day counts and allocations together while retaining dates, sessions, evidence and remarks.", "During reconciliation, confirmation recalculates affected saved Payroll months and Final Payment leave balances, retaining old snapshots and before/after audit."]
    },
    "improvements": {
        "zh-Hant": ["清單涵蓋後續已有月份，避免上月尾段補差仍沿用旧結果；不更改考勤原輸入。", "確認頁防止過期、重複及跨範圍提交；假期與 Payroll 全部成功才保存，失敗整批回滾。", "0 日假期及缺資料記錄不自動更改，保留原記錄撤回／補資料入口。"],
        "zh-Hans": ["清单涵盖后续已有月份，避免上月尾段补差仍沿用旧结果；不更改考勤原输入。", "确认页防止过期、重复及跨范围提交；假期与 Payroll 全部成功才保存，失败整批回滚。", "0 日假期及缺资料记录不自动更改，保留原记录撤回／补资料入口。"],
        "en": ["Include later saved months for forecast reconciliation; attendance inputs stay unchanged.", "Reject stale, repeated and out-of-scope submissions; leave and Payroll changes commit together or roll back together.", "Zero-day and incomplete records require withdrawal or source correction instead of automatic changes."]
    },
    "limitations": {
        "zh-Hant": ["不代表付款或自動更改已下載 Excel，須重新匯出。無既有 Payroll 的月份不建立多餘快照。離職年假補薪只同步結餘差額，保留人工調整、日薪率及其他離職輸入；若調整後負數或資料缺失，整批不保存。"],
        "zh-Hans": ["不代表付款或自动更改已下载 Excel，须重新导出。无既有 Payroll 的月份不建立多余快照。离职年假补薪只同步结余差额，保留人工调整、日薪率及其他离职输入；若调整后负数或资料缺失，整批不保存。"],
        "en": ["No payment or modification of downloaded Excel files; re-export them. Do not create unnecessary snapshots for unsaved months. Final Payment leave-pay days follow balance differences while retaining manual adjustments, rates and other inputs; negative days or missing data block the whole batch."]
    }
},
{
    "version": "V0.5.3", "date": "2026-09-09",
    "title": {"zh-Hant": "請假工作日計算與舊記錄差異核對", "zh-Hans": "请假工作日计算与旧记录差异核对", "en": "Leave workday counting and historical difference review"},
    "features": {
        "zh-Hant": ["年假、病假及無薪假統一按員工適用工作日計算：5／5.5 天制排除六日；6 天制排除星期日，另排除適用假日。", "假期日數差異核對涵蓋全部年度及在職／離職員工，列出原日數、試算日數、差額及相關 Payroll 快照月份。"],
        "zh-Hans": ["年假、病假及无薪假统一按员工适用工作日计算：5／5.5 天制排除六日；6 天制排除星期日，另排除适用假日。", "假期日数差异核对涵盖全部年度及在职／离职员工，列出原日数、试算日数、差额及相关 Payroll 快照月份。"],
        "en": ["Annual, sick and unpaid leave exclude weekends for 5/5.5-day schedules or Sunday for 6-day schedules, plus applicable holidays.", "Read-only historical review covers all years and active/departed employees, showing saved/new days, differences and Payroll snapshot months."]
    },
    "improvements": {
        "zh-Hant": ["假期詳情及錄入視窗沿用考勤的深綠底黃色員工資訊，按請假日期顯示有效 Payroll 類別及合約／請假工作制。", "新增及更正使用伺服器日數預覽，顯示不計假日期；保存逐日計算結果供考勤及 Payroll 共用。", "考勤保留合約工作制：5.5 天制星期六仍計 0.5 天；常駐提示說明與請假計日的差別。", "舊記錄保留原口徑，HR 核對後以原記錄更正；無需重複新增。"],
        "zh-Hans": ["假期详情及录入窗口沿用考勤的深绿底黄色员工信息，按请假日期显示有效 Payroll 类别及合同／请假工作制。", "新增及更正使用服务器日数预览，显示不计假日期；保存逐日计算结果供考勤及 Payroll 共用。", "考勤保留合同工作制：5.5 天制星期六仍计 0.5 天；常驻提示说明与请假计日的差别。", "旧记录保留原口径，HR 核对后以原记录更正；无需重复新增。"],
        "en": ["Leave details and editors use the attendance green/yellow employee banner and show effective Payroll group and contractual/leave workweeks for selected dates.", "Server previews list excluded dates; saved date allocations are shared by attendance and Payroll.", "Contractual Saturday attendance remains 0.5 day for 5.5-day schedules, with permanent explanatory guidance.", "Legacy records retain their basis until explicitly corrected by HR."]
    },
    "limitations": {
        "zh-Hant": ["不自動改寫舊假期或已生成 Payroll 快照；歷史出糧由 HR 核對後另行處理。有效工作制及本地工作日曆須準確。工傷連續計薪規則不變。"],
        "zh-Hans": ["不自动改写旧假期或已生成 Payroll 快照；历史出粮由 HR 核对后另行处理。有效工作制及本地工作日历须准确。工伤连续计薪规则不变。"],
        "en": ["No automatic rewrite of legacy leave or existing Payroll snapshots. HR must reconcile historical pay. Effective schedules and saved calendars must be accurate. Work-injury calendar-day pay is unchanged."]
    }
},
{
    "version": "V0.5.2", "date": "2026-09-09",
    "title": {"zh-Hant": "圖片附件兼容性及請假錯誤保留", "zh-Hans": "图片附件兼容性及请假错误保留", "en": "Image attachment compatibility and leave error recovery"},
    "features": {
        "zh-Hant": ["JPG／JPEG／PNG 按實際格式及完整解碼檢查；可讀 JPEG 不再因結尾附加資料而被誤拒。"],
        "zh-Hans": ["JPG／JPEG／PNG 按实际格式及完整解码检查；可读 JPEG 不再因结尾附加数据而被误拒。"],
        "en": ["Validate JPG/JPEG/PNG by actual format and complete decoding; readable JPEGs with trailing metadata are no longer rejected solely for their ending."]
    },
    "improvements": {
        "zh-Hant": ["假期與工傷沿用員工編輯的錯誤保留機制；失敗時留在視窗內顯示原因，保留已填日期及已選附件。", "保存後返回同一頁時亦刷新歷史及關閉視窗，避免誤以為保存失敗而重複提交。", "仍拒絕偽裝格式、無法解碼的圖片及超過 4,000 萬像素的圖片；保留 32 MB 請求限制，原始附件不轉檔。"],
        "zh-Hans": ["假期与工伤沿用员工编辑的错误保留机制；失败时留在窗口内显示原因，保留已填日期及已选附件。", "保存后返回同一页时亦刷新历史及关闭窗口，避免误以为保存失败而重复提交。", "仍拒绝伪装格式、无法解码的图片及超过 4,000 万像素的图片；保留 32 MB 请求限制，原始附件不转档。"],
        "en": ["Leave and injury editors retain dates and selected files while displaying validation errors in place.", "Same-page successful saves refresh history and close the editor to avoid apparent failures and duplicate submissions.", "Reject disguised formats, undecodable or over-40-megapixel images; retain the 32 MB request limit and original evidence bytes."]
    },
    "limitations": {
        "zh-Hant": ["不變更計薪或假期日數規則；PDF 驗證規則不變。個別正式環境失敗仍需依實際提交及錯誤核查。"],
        "zh-Hans": ["不变更计薪或假期天数规则；PDF 验证规则不变。个别正式环境失败仍需依实际提交及错误核查。"],
        "en": ["No payroll or leave-day changes; PDF validation is unchanged. Unreproduced production failures require the actual submission and error."]
    }
},
{
    "version": "V0.5.1", "date": "2026-09-09",
    "title": {"zh-Hant": "附件錯誤提示精準化", "zh-Hans": "附件错误提示精准化", "en": "Clear attachment validation messages"},
    "features": {
        "zh-Hant": ["附件錯誤列明 .pdf、.jpg、.jpeg、.png、.docx、.xlsx；考勤入口另提示只接受 PDF。"],
        "zh-Hans": ["附件错误列明 .pdf、.jpg、.jpeg、.png、.docx、.xlsx；考勤入口另提示只接受 PDF。"],
        "en": ["Attachment errors list all supported extensions; attendance uploads explicitly accept PDF only."]
    },
    "improvements": {
        "zh-Hant": ["區分格式不支援、驗證失敗、空文件及請求超出 32 MB；不直接斷言附件損壞。", "員工編輯彈窗保留伺服器的具體錯誤內容及原有填寫資料。"],
        "zh-Hans": ["区分格式不支持、验证失败、空文件及请求超过 32 MB；不直接断言附件损坏。", "员工编辑弹窗保留服务器的具体错误内容及原有填写资料。"],
        "en": ["Distinguish unsupported format, validation failure, empty files and the 32 MB request limit without assuming corruption.", "Employee editors retain the specific server error along with entered fields."]
    },
    "limitations": {
        "zh-Hant": ["不新增支援格式、不放寬驗證、不更改員工或病假資料；個別附件被拒原因仍須原檔核實。"],
        "zh-Hans": ["不新增支持格式、不放宽验证、不更改员工或病假资料；个别附件被拒原因仍须原文件核实。"],
        "en": ["No new formats, relaxed validation or employee/leave data changes. A specific rejection still requires the original file to diagnose."]
    }
},
{
    "version": "V0.5.0",
    "date": "2026-09-07",
    "title": {
        "zh-Hant": "員工編輯防誤操作與附件總庫精簡",
        "zh-Hans": "员工编辑防误操作与附件总库精简",
        "en": "Safer employee editing and a lean document library"
    },
    "features": {
        "zh-Hant": [
            "員工及文件核對表單有未保存修改時，關閉、切換及離開前提醒；未修改則不打擾。",
            "保存校驗失敗時保留本頁欄位及所選附件，顯示具體錯誤；網絡結果不明時提示先查歷史，避免重複新增。",
            "合約與附件改為類別／數量篩選及一張文件列表；空類別不再標紅，SHA-256 收入文件詳情。"
        ],
        "zh-Hans": [
            "员工及文件核对表单有未保存修改时，关闭、切换及离开前提醒；未修改则不打扰。",
            "保存校验失败时保留本页字段及所选附件，显示具体错误；网络结果不明时提示先查历史，避免重复新增。",
            "合同与附件改为类别／数量筛选及一张文件列表；空类别不再标红，SHA-256 收入文件详情。"
        ],
        "en": [
            "Warn before discarding changed employee or document-review forms; untouched forms need no confirmation.",
            "Validation errors retain fields and selected files in the open page. Unknown network outcomes prompt a history check before retrying.",
            "Category/count filters and one document list replace repeated file cards. Empty categories are neutral; hashes move into details."
        ]
    },
    "improvements": {
        "zh-Hant": [
            "表單內說明新增、更正、替換附件、補交憑證和作廢的差別；續證新增、日期填錯更正。",
            "入職、離職、轉正、薪酬生效日期及工作制等改動時，顯示相關影響及歷史月份核對提示，不增加審批步驟。",
            "保存成功沿用原頁面及成功訊息；繁體、簡體、英文共用相同操作。",
            "修正變更歷史及共用操作欄的橫線對齊；生效日期欄只顯示起始日，截止日期在內容另行標示，不改歷史計薪資料。"
        ],
        "zh-Hans": [
            "表单内说明新增、更正、替换附件、补交凭证和作废的区别；续证新增、日期填错更正。",
            "入职、离职、转正、薪酬生效日期及工作制等改动时，显示相关影响及历史月份核对提示，不增加审批步骤。",
            "保存成功沿用原页面及成功消息；繁体、简体、英文共用相同操作。",
            "修正变更历史及共用操作栏的横线对齐；生效日期栏只显示起始日，截止日期在内容另行标示，不改历史计薪资料。"
        ],
        "en": [
            "Contextual action guidance distinguishes new records, corrections, replacement, evidence and voiding, including credential renewal.",
            "Important employment, probation, pay dates and workweek changes show impact hints without new approval steps.",
            "Successful saves retain existing destinations and flash messages across all three languages.",
            "Align history and shared action-column row borders. Show only the effective start in the date column and label the end in record content, without changing historical pay data."
        ]
    },
    "limitations": {
        "zh-Hant": ["不新增草稿資料庫或瀏覽器持久儲存；關閉頁面後不保證恢復。", "不改計薪公式、不重寫歷史考勤／Payroll、不新增關帳、審批或任務系統。"],
        "zh-Hans": ["不新增草稿数据库或浏览器持久存储；关闭页面后不保证恢复。", "不改计薪公式、不重写历史考勤／Payroll、不新增关账、审批或任务系统。"],
        "en": ["Drafts stay in the open page only, with no persistent browser or database draft storage.", "No pay-formula changes, historical rewrites, payroll closing, approvals or task system."]
    }
},
{
    "version": "V0.4.0",
    "date": "2026-09-07",
    "title": {
        "zh-Hant": "員工資料與附件管理一致性完善",
        "zh-Hans": "员工资料与附件管理一致性完善",
        "en": "Consistent employee records and evidence workflows"
    },
    "features": {
        "zh-Hant": [
            "病假待補憑證直接定位原請假記錄；獨立補交附件，不新增假期或更改日數。",
            "證件卡片與看板共用到期判斷，提醒直接定位證件，並涵蓋有到期日的專業資歷。",
            "附件替換須選定一份原件及填寫原因，保留歷史並統一更新所屬資料引用。"
        ],
        "zh-Hans": [
            "病假待补凭证直接定位原请假记录；独立补交附件，不新增假期或更改日数。",
            "证件卡片与看板共用到期判断，提醒直接定位证件，并涵盖有到期日的专业资历。",
            "附件替换须选定一份原件及填写原因，保留历史并统一更新所属资料引用。"
        ],
        "en": [
            "Missing sick-leave evidence opens the existing record; evidence-only changes do not create leave.",
            "Credential cards and dashboard share expiry rules and direct links, including dated qualifications.",
            "Replacement targets one document with a reason; history and typed references are preserved."
        ]
    },
    "improvements": {
        "zh-Hant": [
            "合約核對預填現有年假及試用期；僅明確勾選更新條款才套用，空白不清除既有值。",
            "統一證件重複與日期校驗；Staff Record 更新個人、學歷及入職日期均寫入相應變更歷史。",
            "工作／安全證件與學歷／專業資歷分區展示；既有資料不搬移或刪除。",
            "統一彈窗欄位、文件選擇、提示與取消按鈕名稱；新增員工必須自行選擇 Payroll 類別，轉正資料缺失明示待核實。"
        ],
        "zh-Hans": [
            "合同核对预填现有年假及试用期；仅明确勾选更新条款才应用，空白不清除已有值。",
            "统一证件重复与日期校验；Staff Record 更新个人、学历及入职日期均写入相应变更历史。",
            "工作／安全证件与学历／专业资历分区展示；已有资料不搬移或删除。",
            "统一弹窗字段、文件选择、提示与取消按钮名称；新增员工须自行选择 Payroll 类别，转正资料缺失明示待核实。"
        ],
        "en": [
            "Contract review preserves leave/probation terms unless explicitly applied; blank fields preserve existing values.",
            "Shared duplicate/date validation and source-specific audit history for Staff Record changes.",
            "Work/safety credentials and education/qualifications are presented separately without migrating records.",
            "Consistent dialogs and file inputs; explicit Payroll-group selection and unverified probation copy."
        ]
    },
    "limitations": {
        "zh-Hant": [
            "不批量更改正式員工、既有假期、附件分類或歷史 Payroll；缺失資料仍須 HR 核對補齊。",
            "不新增 OCR、任務系統或審批流程；本版不改動 Payroll 計薪公式。"
        ],
        "zh-Hans": [
            "不批量更改正式员工、已有假期、附件分类或历史 Payroll；缺失资料仍须 HR 核对补齐。",
            "不新增 OCR、任务系统或审批流程；本版不改动 Payroll 计薪公式。"
        ],
        "en": [
            "No bulk edits to employee records, leave, document categories or historical Payroll.",
            "No OCR, task system, approval workflow or Payroll formula changes."
        ]
    }
},
    {
        "version": "V0.3.11",
        "date": "2026-09-06",
        "limitations": {
            "zh-Hant": ["不會批量改寫既有假期或已匯出的歷史 Payroll；受影響記錄須由 HR 核對來源後重新匯出。", "考勤只有分段總日數，不能自行判斷某天是否已被 HR 排除，故假期變更只提示重新核對。"],
            "zh-Hans": ["不会批量改写已有假期或已导出的历史 Payroll；受影响记录须由 HR 核对来源后重新导出。", "考勤只有分段总日数，不能自行判断某天是否已被 HR 排除，因此假期变更只提示重新核对。"],
            "en": ["Existing leave and exported historical Payroll are not rewritten in bulk; HR must review affected sources and re-export.", "Segment totals do not identify individual attendance dates, so leave changes prompt review rather than automatically reducing attendance."]},
        "title": {"zh-Hant": "假期、補休與 Payroll 一致性修正", "zh-Hans": "假期、补休与 Payroll 一致性修正", "en": "Leave, compensation leave and Payroll consistency"},
        "features": {
            "zh-Hant": ["請假日數按日期及上午／下午自動計算；新增、更正時阻止假期及工傷時段重疊。", "考勤保存後新增、更正或撤回假期／工傷，會在考勤及 Payroll 提示重新核對，不會自動更改已錄入出勤。"],
            "zh-Hans": ["请假日数按日期及上午／下午自动计算；新增、更正时阻止假期及工伤时段重叠。", "考勤保存后新增、更正或撤回假期／工伤，会在考勤及 Payroll 提示重新核对，不会自动更改已录入出勤。"],
            "en": ["Leave days are derived from dates and AM/PM; overlapping leave and injury periods are rejected on creation and correction.", "Leave/injury changes after saved attendance prompt review in Attendance and Payroll without automatically changing attendance."]},
        "improvements": {
            "zh-Hant": ["修正三種 XLSX 的病假／工傷平均計薪率被普通日薪率覆蓋，保留首日全薪、4/5及全薪工傷的實際混合計薪率。", "不變的考勤補休來源在重存後保留原記錄及扣假分帳；真正變更時於同一交易重分配，餘額不足則不保存。", "未保存的預填不再標成已保存或無需補差；上月尾段明確提示待按 PDF 核對。", "項目薪酬摘要補列其他款項／補差，OT及E-CALL包含上月尾段，分項可加回總額。", "假期歷史顯示上午／下午；既有假期日期與日數矛盾或重疊時，提示先更正再出糧，不批量改寫歷史資料。"],
            "zh-Hans": ["修正三种 XLSX 的病假／工伤平均计薪率被普通日薪率覆盖，保留首日全薪、4/5及全薪工伤的实际混合计薪率。", "不变的考勤补休来源在重存后保留原记录及扣假分账；真正变更时在同一交易重分配，余额不足则不保存。", "未保存的预填不再标成已保存或无需补差；上月尾段明确提示待按 PDF 核对。", "项目薪酬摘要补列其他款项／补差，OT及E-CALL包含上月尾段，分项可加回总额。", "假期历史显示上午／下午；已有假期日期与日数矛盾或重叠时，提示先更正再出薪，不批量改写历史资料。"],
            "en": ["All three XLSX exports preserve the effective sick/injury rate, including first-day full pay, four-fifths and full-pay injury combinations.", "Unchanged attendance preserves credit IDs and leave allocations; genuine changes reconcile atomically and insufficient balances prevent saving.", "Unsaved prefills no longer claim saved attendance or no reconciliation required.", "Project summaries include other pay and reconciliation, plus prior-tail OT/E-CALL, so visible components reconcile.", "Leave history shows AM/PM. Inconsistent legacy dates/days or overlaps require correction before Payroll, without bulk rewriting history."]},
    },
    {
        "version": "V0.3.10",
        "date": "2026-09-01",
        "title": {
            "zh-Hant": "年假帳戶扣減核對修正",
            "zh-Hans": "年假账户扣减核对修正",
            "en": "Annual-leave bucket reconciliation fix",
        },
        "features": {
            "zh-Hant": [
                "假期記錄會顯示每筆年假實際扣自補休、2023及以前或指定年度年假帳戶，方便 HR 直接核對來源。",
                "假期詳情套用員工檔案的一致模式：上方分為本年度年假、2023及以前及補休三張當前狀態卡片，下方集中顯示假期變更歷史。",
                "新增請假改為唯一彈窗入口；年假額度調整、舊年假總額調整、更正、撤回及補交憑證均在所屬卡片或歷史記錄操作。",
            ],
            "zh-Hans": [
                "假期记录会显示每笔年假实际扣自补休、2023及以前或指定年度年假账户，方便 HR 直接核对来源。",
                "假期详情套用员工档案的一致模式：上方分为本年度年假、2023及以前及补休三张当前状态卡片，下方集中显示假期变更历史。",
                "新增请假改为唯一弹窗入口；年假额度调整、旧年假总额调整、更正、撤回及补交凭证均在所属卡片或历史记录操作。",
            ],
            "en": [
                "Each annual-leave record now shows whether it was deducted from compensation leave, the pre-2024 balance, or a specific annual bucket.",
                "Leave details now follow the employee-profile pattern with three current-state cards above one consolidated change history.",
                "A single Add Leave dialog is joined by scoped balance adjustments and history-row correction, withdrawal, and evidence actions.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "修正同一筆年假已扣舊年假或補休後又被本年度帳戶重複計入的問題；本年已放總數與本年度帳戶用量分開計算，離職 Payroll 亦沿用正確帳戶餘額。",
                "2023及以前年假在同一張卡片清楚列出已確認總額、已扣除及目前剩餘，消除50.5總額與50.0剩餘看似矛盾的情況。",
                "補休取得來源及年假額度調整納入同一變更歷史；本年度與舊年假調整互相獨立，不會因修改其中一項而改寫另一項。",
                "假期變更歷史統一按香港時間顯示及排序；假期日期移至內容欄，單日只顯示一次日期，多日才顯示起訖。",
                "日工考勤提示明確區分預填暫按星期日不上班與實際星期日上班須計入出勤；不改動預填或計薪規則。",
            ],
            "zh-Hans": [
                "修正同一笔年假已扣旧年假或补休后又被本年度账户重复计入的问题；本年已休总数与本年度账户用量分开计算，离职 Payroll 也沿用正确账户余额。",
                "2023及以前年假在同一张卡片清楚列出已确认总额、已扣除及目前剩余，消除50.5总额与50.0剩余看似矛盾的情况。",
                "补休取得来源及年假额度调整纳入同一变更历史；本年度与旧年假调整互相独立，不会因修改其中一项而改写另一项。",
                "假期变更历史统一按香港时间显示及排序；假期日期移至内容栏，单日只显示一次日期，多日才显示起止。",
                "日工考勤提示明确区分预填暂按星期日不上班与实际星期日上班须计入出勤；不改动预填或计薪规则。",
            ],
            "en": [
                "A leave record consumed from an older or compensation balance is no longer counted again in the current-year bucket. Calendar-year leave taken and current-bucket usage are calculated separately, including final Payroll.",
                "The pre-2024 card now places confirmed total, consumed days, and remaining days together, removing ambiguity between 50.5 total and 50.0 remaining.",
                "Comp-leave sources and balance adjustments join the history; current-year and legacy adjustments are isolated from each other.",
                "Leave history is now sorted and displayed in Hong Kong time; leave dates are shown in the content column, with single-day ranges collapsed to one date.",
                "Daily-worker hints now distinguish the Sunday-off prefill assumption from recording Sundays actually worked; prefill and pay rules are unchanged.",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "扣減次序維持補休、2023及以前、最早到期的2024年起年假；本修正不改寫既有請假或扣減記錄。",
                "補休仍只能由考勤錄入產生；本頁只提供查看來源，不新增第二個手動入口。",
            ],
            "zh-Hans": [
                "扣减次序维持补休、2023及以前、最早到期的2024年起年假；本修正不改写现有请假或扣减记录。",
                "补休仍只能由考勤录入产生；本页只提供查看来源，不新增第二个手动入口。",
            ],
            "en": [
                "Deduction priority remains compensation leave, pre-2024 balance, then the oldest valid 2024+ bucket. Existing leave and allocation records are not rewritten.",
                "Comp leave still originates only from Attendance Entry; this page shows its source without adding a second manual-entry path.",
            ],
        },
    },
    {
        "version": "V0.3.9",
        "date": "2026-08-28",
        "title": {
            "zh-Hant": "統一員工文件入口與專項分流",
            "zh-Hans": "统一员工文件入口与专项分流",
            "en": "Unified employee document intake and owned-record routing",
        },
        "features": {
            "zh-Hant": [
                "合約與附件新增唯一的「上傳文件」入口；HR 先選用途，Staff Record、三寶、已簽雇傭合約、CV 及一般附件可直接上傳核對。",
                "銀行、證件、任職薪酬、轉正、假期、工傷、考勤、離職及改名憑證會自動前往所屬專項模組，避免附件與業務記錄脫節。",
                "資料選項新增「一般附件類型」，HR 可維護推薦信、培訓記錄、員工聲明等公司自訂分類。",
            ],
            "zh-Hans": [
                "合同与附件新增唯一的“上传文件”入口；HR 先选用途，Staff Record、三宝、已签雇佣合同、CV 及一般附件可直接上传核对。",
                "银行、证件、任职薪酬、转正、假期、工伤、考勤、离职及改名凭证会自动前往所属专项模块，避免附件与业务记录脱节。",
                "资料选项新增“一般附件类型”，HR 可维护推荐信、培训记录、员工声明等公司自定义分类。",
            ],
            "en": [
                "Contracts & Attachments now has one Upload document gateway for Staff Record, Three Treasures, signed contracts, CVs and general files.",
                "Bank, credential, employment/pay, probation, leave, work-injury, attendance, termination and name-change evidence routes to its owning record instead of creating an orphan file.",
                "General attachment types are configurable in Data Options for company-specific file classification.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "個人資料、證件與資歷及任職與薪酬加入同一入口的用途快捷按鈕；附件總覽及員工資料匯出會顯示一般附件細分類與憑證的實際標題。",
                "系統文件用途維持固定，只開放一般附件細分類供 HR 維護，保留 Payroll、假期、提醒及審計所需的穩定資料語義。",
                "Staff Record 人工核對補齊住址、緊急聯絡、學歷及入職資料，銀行資料會建立有生效日期的正式記錄；核對欄位沿用考勤錄入的字體、輸入框及提示風格。",
            ],
            "zh-Hans": [
                "个人资料、证件与资历及任职与薪酬加入同一入口的用途快捷按钮；附件总览及员工资料导出会显示一般附件细分类与凭证的实际标题。",
                "系统文件用途保持固定，只开放一般附件细分类供 HR 维护，保留 Payroll、假期、提醒及审计所需的稳定资料语义。",
                "Staff Record 人工核对补齐住址、紧急联系人、学历及入职资料，银行资料会建立有生效日期的正式记录；核对栏位沿用考勤录入的字体、输入框及提示风格。",
            ],
            "en": [
                "Personal, Credentials and Employment offer shortcuts into the same gateway; the file library and employee export show accurate general subtypes and evidence titles.",
                "System purposes remain fixed while only general subtypes are editable, preserving stable Payroll, leave, reminder and audit semantics.",
                "Staff Record review now captures address, emergency contact, education and employment-start data, creates effective-dated bank records, and reuses Attendance Entry field styling.",
            ],
        },
        "limitations": {
            "zh-Hant": ["本版本不使用 OCR；HR 仍須預覽來源文件並人工核對結構化資料。"],
            "zh-Hans": ["本版本不使用 OCR；HR 仍须预览来源文件并人工核对结构化资料。"],
            "en": ["OCR remains outside this release; HR previews source documents and confirms structured data manually."],
        },
    },
    {
        "version": "V0.3.8",
        "date": "2026-08-21",
        "title": {
            "zh-Hant": "下一年度日曆準備與考勤介面精簡",
            "zh-Hans": "下一年度日历准备与考勤界面精简",
            "en": "Next-year calendar preparation and cleaner attendance entry",
        },
        "features": {
            "zh-Hant": [
                "工作日曆自動把主要帶入操作指向下一年度；2026 年顯示 2027 年，進入 2027 年後自動改為 2028 年。",
            ],
            "zh-Hans": [
                "工作日历自动把主要导入操作指向下一年度；2026 年显示 2027 年，进入 2027 年后自动改为 2028 年。",
            ],
            "en": [
                "Work Calendar now targets the next calendar year automatically: 2026 prepares 2027, then 2027 prepares 2028.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "已存在下一年度記錄時，按鈕改為「核對並補齊」，仍只補充缺少日期及適用範圍；考勤月份與員工搜尋區移除重複提示並壓縮高度，月份框整個範圍均可打開選擇器。",
            ],
            "zh-Hans": [
                "下一年度已有记录时，按钮改为“核对并补齐”，仍只补充缺少日期及适用范围；考勤月份与员工搜索区移除重复提示并压缩高度，月份框整个范围均可打开选择器。",
            ],
            "en": [
                "When next-year records already exist, the action changes to Check and complete without overwriting HR data. Redundant attendance hints were removed, and the whole month field now opens its picker.",
            ],
        },
        "limitations": {
            "zh-Hant": ["官方尚未公布下一年度清單時，系統不會建立推測資料；HR 稍後重新執行即可。"],
            "zh-Hans": ["官方尚未公布下一年度清单时，系统不会建立推测资料；HR 稍后重新执行即可。"],
            "en": ["If official next-year lists are not yet available, the system does not create estimated dates; HR can retry later."],
        },
    },
    {
        "version": "V0.3.7",
        "date": "2026-08-21",
        "title": {
            "zh-Hant": "法定假日與公眾假期分流",
            "zh-Hans": "法定假日与公众假期分流",
            "en": "Payroll-category holiday calendars",
        },
        "features": {
            "zh-Hant": [
                "工作日曆分開記錄香港法定假日與公眾假期；地盤日工／月工自動使用法定假日，管理人員及總部人員自動使用公眾假期。",
                "香港假日日曆按年份一次帶入兩套官方清單；公司固定採用聖誕節，不再要求 HR 每年選擇冬節或聖誕節。",
            ],
            "zh-Hans": [
                "工作日历分开记录香港法定假日与公众假期；地盘日工／月工自动使用法定假日，管理人员及总部人员自动使用公众假期。",
                "香港假日日历按年份一次导入两套官方清单；公司固定采用圣诞节，不再要求 HR 每年选择冬节或圣诞节。",
            ],
            "en": [
                "Work Calendar now distinguishes Hong Kong statutory holidays from general holidays. Site Daily/Monthly use statutory holidays while Management/Head Office use general holidays.",
                "One annual Hong Kong import retrieves both official schedules. Company policy fixes Christmas Day, removing the annual Winter Solstice/Christmas choice from HR.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "員工任職資料只讀顯示適用假日日曆；考勤橫幅、輸入欄提示及 Payroll 計算規則亦按 Payroll 類別顯示法定假日或公眾假期。",
                "OFFICE 月底預估會排除政府公眾假期及補假；日工法定假日薪酬仍只按法定假日計算，兩套規則不會混用。",
            ],
            "zh-Hans": [
                "员工任职资料只读显示适用假日日历；考勤横幅、输入栏提示及 Payroll 计算规则也按 Payroll 类别显示法定假日或公众假期。",
                "OFFICE 月底预计会排除政府公众假期及补假；日工法定假日薪酬仍只按法定假日计算，两套规则不会混用。",
            ],
            "en": [
                "Employment details show the derived calendar read-only; Attendance context, field guidance and Payroll rules use the correct holiday terminology for the Payroll category.",
                "OFFICE forecasts exclude gazetted general holidays and substitution days, while daily statutory-holiday pay remains limited to statutory dates.",
            ],
        },
        "limitations": {
            "zh-Hant": ["自動帶入目前只適用香港工作地區；其他地區仍由 HR 按當地官方規則維護。已保存考勤不會自動改寫。"],
            "zh-Hans": ["自动导入目前只适用于香港工作地区；其他地区仍由 HR 按当地官方规则维护。已保存考勤不会自动改写。"],
            "en": ["Automatic import currently applies only to Hong Kong. HR maintains other regions from their official rules, and saved attendance is never rewritten."],
        },
    },
    {
        "version": "V0.3.6",
        "date": "2026-08-21",
        "title": {
            "zh-Hant": "日工核對基準與法定假日帶入",
            "zh-Hans": "日工核对基准与法定假日导入",
            "en": "Daily-worker review baseline and statutory-holiday import",
        },
        "features": {
            "zh-Hant": [
                "日工未保存的四段考勤改為按星期一至六預填；星期日及法定假日預設沒有出勤，HR 只在對照 PDF 後加入真正發生的工作。",
                "工作日曆新增「帶入香港法定假日」，按年份從勞工處年度清單加入本地日曆；冬節或聖誕節由 HR 依公司安排明確選擇。",
            ],
            "zh-Hans": [
                "日工未保存的四段考勤改为按星期一至六预填；星期日及法定假日默认没有出勤，HR 只在对照 PDF 后加入真正发生的工作。",
                "工作日历新增“导入香港法定假日”，按年份从劳工处年度清单加入本地日历；冬节或圣诞节由 HR 依公司安排明确选择。",
            ],
            "en": [
                "Unsaved daily-worker attendance now prefills Monday-Saturday. Sunday and statutory-holiday work start at zero and are added only after HR reviews the PDF.",
                "Work Calendar can import a selected year's Hong Kong statutory holidays from the Labour Department, with an explicit employer choice between Winter Solstice and Christmas Day.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "日工預填會排除已登記年假、病假、無薪假及工傷；這些日期不算實際出勤，Payroll 依假別另行計薪，避免年假日同時算出勤而重複支付。",
                "帶入只新增缺少日期，不覆蓋或恢復既有記錄；考勤及 Payroll 仍只依本地工作日曆計算，不在出糧時連線下載。",
            ],
            "zh-Hans": [
                "日工预填会排除已登记年假、病假、无薪假及工伤；这些日期不算实际出勤，Payroll 依假别另行计薪，避免年假日同时算出勤而重复支付。",
                "导入只新增缺少日期，不覆盖或恢复既有记录；考勤及 Payroll 仍只依本地工作日历计算，不在发薪时联网下载。",
            ],
            "en": [
                "Daily prefills exclude recorded annual leave, sick leave, unpaid leave and work injury. These dates are not attendance and Payroll applies their own rules, preventing duplicate annual-leave pay.",
                "Import adds missing dates only and never overwrites or restores existing records. Attendance and Payroll continue to calculate from the local Work Calendar without a live export-time dependency.",
            ],
        },
        "limitations": {
            "zh-Hant": ["自動帶入目前只適用香港工作地區；其他地區仍須由 HR 依官方資料維護。既有已保存考勤不會被自動改寫。"],
            "zh-Hans": ["自动导入目前只适用于香港工作地区；其他地区仍须由 HR 依官方资料维护。既有已保存考勤不会被自动改写。"],
            "en": ["Automatic import currently applies only to Hong Kong. HR maintains other regions from their official sources, and existing saved attendance is never rewritten."],
        },
    },
    {
        "version": "V0.3.5",
        "date": "2026-08-21",
        "title": {
            "zh-Hant": "四段考勤表格化與異常驅動錄入",
            "zh-Hans": "四段考勤表格化与异常驱动录入",
            "en": "Table-based four-part attendance and exception-led entry",
        },
        "features": {
            "zh-Hant": [
                "考勤詳情把本月實際、本月預估、上月實際及上月原預估改為兩組四行摘要表；每行先顯示出勤、工作制外／法定假日、OT／E-CALL及其他津貼，只有按修改才展開原有欄位。",
                "取消只重複下方輸入數字的「本次 Payroll 核對」總計；上月尾段改為直接比較實際與原預估，沒有差額時清楚顯示無需補差，有差額時只列出發生變化的項目。",
            ],
            "zh-Hans": [
                "考勤详情把本月实际、本月预计、上月实际及上月原预计改为两组四行摘要表；每行先显示出勤、工作制外／法定假日、OT／E-CALL及其他津贴，只有按修改才展开原有字段。",
                "取消只重复下方输入数字的“本次 Payroll 核对”总计；上月尾段改为直接比较实际与原预计，没有差额时明确显示无需补差，有差额时只列出发生变化的项目。",
            ],
            "en": [
                "Attendance detail now presents current actual, current forecast, prior actual and prior original forecast as two compact four-row tables. Each row summarizes attendance, outside-workweek or statutory-holiday work, OT/E-CALL and other allowance, expanding the existing fields only when edited.",
                "The duplicate Payroll-check total is removed. The prior-month tail now compares actual against original forecast directly, stating when no adjustment is needed and listing only changed items when differences exist.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "計算規則收進可展開說明；假期／工傷摘要維持明確類別及更正入口，但明細改為按需展開。系統基準只標示為待按 PDF 核對，不會誤稱系統已判定無異常。",
                "保留一次保存四段、跨項目分配、日期選擇、出薪／補休及原有審計資料；新增 Ctrl+Enter 快捷鍵保存目前考勤。",
            ],
            "zh-Hans": [
                "计算规则收进可展开说明；假期／工伤摘要保留明确类别及更正入口，但明细改为按需展开。系统基准只标记为待按 PDF 核对，不会误称系统已判定无异常。",
                "保留一次保存四段、跨项目分配、日期选择、出薪／补休及原有审计资料；新增 Ctrl+Enter 快捷键保存当前考勤。",
            ],
            "en": [
                "Calculation rules move into an expandable disclosure. Leave/work-injury keeps explicit types and its correction link while details expand only when needed. A generated baseline is labelled as awaiting PDF review, never as a system-confirmed absence of exceptions.",
                "One-save four-part persistence, cross-project allocation, date selection, Payroll/Comp Leave treatment and the existing audit trail are retained. Ctrl+Enter now saves the current attendance form.",
            ],
        },
        "limitations": {
            "zh-Hant": ["系統不會解讀考勤 PDF 或自動判斷無異常；HR 保存前仍須以簽署 PDF 核對實際資料。"],
            "zh-Hans": ["系统不会解读考勤 PDF 或自动判断无异常；HR 保存前仍须以签署 PDF 核对实际资料。"],
            "en": ["The system does not interpret the attendance PDF or automatically certify that there are no exceptions; HR must still review the signed PDF before saving."],
        },
    },
    {
        "version": "V0.3.4",
        "date": "2026-08-20",
        "title": {
            "zh-Hant": "考勤核對簡化與歸屬保護",
            "zh-Hans": "考勤核对简化与归属保护",
            "en": "Simplified attendance review and assignment protection",
        },
        "features": {
            "zh-Hant": [
                "考勤詳情按「本月考勤」及「上月尾段核對」分組，仍保留原有四段資料與一次保存，不增加核對狀態或另一套工作流程。",
                "原本把四段全部相加的摘要改為 Payroll 核對行：日工及例外月薪顯示本月加上月尾段差額的基本計薪日數；標準月薪則清楚標示基本薪金按整月合約薪金計算，並分開顯示 OT、大 E-CALL及普通 E-CALL。",
                "已保存考勤的員工及月份預設鎖定；網址參數不再覆蓋其歸屬。只有按「更正員工／月份」才顯示更正欄位，保存後沿用既有文件歸檔及審計記錄。",
            ],
            "zh-Hans": [
                "考勤详情按“本月考勤”及“上月尾段核对”分组，仍保留原有四段资料与一次保存，不增加核对状态或另一套工作流程。",
                "原本把四段全部相加的摘要改为 Payroll 核对行：日工及例外月薪显示本月加上月尾段差额的基本计薪日数；标准月薪则清楚标示基本工资按整月合同工资计算，并分开显示 OT、大 E-CALL及普通 E-CALL。",
                "已保存考勤的员工及月份默认锁定；网址参数不再覆盖其归属。只有按“更正员工／月份”才显示更正字段，保存后沿用既有文件归档及审计记录。",
            ],
            "en": [
                "Attendance detail is grouped into Current-month attendance and Prior-month tail check while retaining the same four stored periods and one save action, with no new review status or parallel workflow.",
                "The incorrect all-positive four-period total is replaced by a Payroll check line. Daily and attendance-prorated monthly staff see current days plus the prior-tail difference; standard monthly staff see that base pay remains full-month contract salary, with OT and both E-CALL types separated.",
                "Saved attendance keeps its employee and month locked against URL overrides. Employee/month controls appear only through Correct employee/month, and saving continues to use the existing document-filing and audit trail.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "綠色橫幅把星期日及法定假日合併到「當前考勤月份」同一行，以日期數字簡潔顯示；2026年7月1日香港特別行政區成立紀念日已補入香港工作日曆。",
                "刪除重複文件標題、四段重複說明、考勤頁轉項目表單、底部重複退出按鈕及空備註顯示的 None；上月考勤 PDF 按鈕移至上月尾段分組標題。",
                "考勤詳情重新分配為較窄的 PDF 預覽及較寬的錄入表單；月份與員工選擇並成一行。本月實際／預估在上方左右並排，上月實際／原預估在下方左右並排；第一行橫幅只保留退出、上一份及保存並下一份，第二行同時顯示員工、Payroll 資料及所屬項目。",
                "四段不再重複顯示項目下拉框或新增按鈕；系統按有效任職資料帶入項目，只有真正跨項目工作才打開分配彈窗。考勤備註同步顯示於員工月份考勤記錄，並在 Payroll XLSX 第一個項目行的備註欄匯出一次。",
                "假期／工傷聯動改為緊湊的黃色核對摘要，標題分別列明年假、病假、無薪假及工傷筆數，只顯示相關日期、計薪影響及唯一更正入口；Payroll 說明卡亦刪除頂部橫幅已有的類別、計薪方式及工作制重複資料，只保留實際填寫與計薪提示。",
            ],
            "zh-Hans": [
                "绿色横幅把星期日及法定假日合并到“当前考勤月份”同一行，以日期数字简洁显示；2026年7月1日香港特别行政区成立纪念日已补入香港工作日历。",
                "删除重复文件标题、四段重复说明、考勤页转项目表单、底部重复退出按钮及空备注显示的 None；上月考勤 PDF 按钮移至上月尾段分组标题。",
                "考勤详情重新分配为较窄的 PDF 预览及较宽的录入表单；月份与员工选择合成一行。本月实际／预计在上方左右并排，上月实际／原预计在下方左右并排；第一行横幅只保留退出、上一份及保存并下一份，第二行同时显示员工、Payroll 资料及所属项目。",
                "四段不再重复显示项目下拉框或新增按钮；系统按有效任职资料带入项目，只有真正跨项目工作才打开分配弹窗。考勤备注同步显示于员工月份考勤记录，并在 Payroll XLSX 第一个项目行的备注栏导出一次。",
                "假期／工伤联动改为紧凑的黄色核对摘要，标题分别列明年假、病假、无薪假及工伤笔数，只显示相关日期、计薪影响及唯一更正入口；Payroll 说明卡也删除顶部横幅已有的类别、计薪方式及工作制重复资料，只保留实际填写与计薪提示。",
            ],
            "en": [
                "The green banner merges Sundays and statutory holidays into the attendance-month line using compact day numbers. Hong Kong SAR Establishment Day on 1 July 2026 is added to the Hong Kong Work Calendar.",
                "Duplicate file headings, repeated four-period explanations, the attendance-page project-transfer form, duplicate bottom exit action and literal None remarks are removed. The prior attendance PDF action moves to the prior-tail group heading.",
                "Attendance detail gives less width to the PDF and more to the entry form, with month and employee selection on one line. Current actual/forecast periods sit side by side above the prior actual/original forecast pair. The banner's first line keeps only exit, previous and save-and-next actions; its second line shows employee, Payroll context and assignment project.",
                "The four periods no longer repeat project selectors or add-row buttons. Effective assignments supply the project, and only genuine cross-project work opens the allocation dialog. Attendance remarks appear in the employee's monthly attendance history and export once on the first project line of the Payroll workbook.",
                "Leave and work-injury linkage now uses one compact yellow review summary. Its title lists annual leave, sick leave, unpaid leave and work-injury counts separately, and it shows only relevant dates, pay impact and the single correction path. The Payroll guidance card also removes category, pay-method and workweek details already present in the top banner, retaining only entry and pay guidance.",
            ],
        },
        "limitations": {
            "zh-Hant": ["工作日曆仍由 HR 按官方資料維護；V0.3.4只補正已確認缺失的2026年7月1日香港法定假日。"],
            "zh-Hans": ["工作日历仍由 HR 按官方资料维护；V0.3.4只补正确认缺失的2026年7月1日香港法定假日。"],
            "en": ["HR still maintains the Work Calendar from official sources. V0.3.4 only corrects the confirmed missing Hong Kong statutory holiday on 1 July 2026."],
        },
    },
    {
        "version": "V0.3.3",
        "date": "2026-08-20",
        "title": {
            "zh-Hant": "智能考勤基準與日工星期日規則",
            "zh-Hans": "智能考勤基准与日工星期日规则",
            "en": "Guided attendance baselines and daily Sunday rules",
        },
        "features": {
            "zh-Hant": [
                "考勤四段在沒有保存資料時，按所選年月、有效項目、Payroll 類別、月薪計薪方式、5／5.5／6 天工作制及工作日曆建立核對基準；OT及 E-CALL 維持 0，上月已保存的月底預估會優先帶入。",
                "日工的非法定假日實際出勤包含星期日；星期日沒有上班不計薪。法定假日實際工作改用獨立欄位及只限法定假日的日期選擇器。",
                "綠色考勤月份橫幅以較大字體同時顯示員工、Payroll 類別、月薪計薪方式／每週工作制、星期日及法定假日，方便全程核對。",
            ],
            "zh-Hans": [
                "考勤四段在没有保存资料时，按所选年月、有效项目、Payroll 类别、月薪计薪方式、5／5.5／6 天工作制及工作日历建立核对基准；OT及 E-CALL 维持 0，上月已保存的月底预计会优先带入。",
                "日工的非法定假日实际出勤包含星期日；星期日没有上班不计薪。法定假日实际工作改用独立字段及只限法定假日的日期选择器。",
                "绿色考勤月份横幅以较大字体同时显示员工、Payroll 类别、月薪计薪方式／每周工作制、星期日及法定假日，方便全程核对。",
            ],
            "en": [
                "Unsaved four-part attendance sections receive a review baseline from the selected month, effective project, Payroll group, monthly pay method, 5/5.5/6-day workweek and Work Calendar. OT and E-CALL remain zero, and a prior saved tail forecast is preferred.",
                "Daily-worker non-statutory-holiday attendance includes Sundays, while an unworked Sunday is unpaid. Actual statutory-holiday work now has a separate field and statutory-holiday-only date picker.",
                "The green attendance-month banner uses larger text and keeps employee, Payroll group, monthly pay method/workweek, Sundays and statutory holidays visible together.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "每個出勤及休息日／法定假日欄按日工、例外月薪及 5／5.5／6 天制顯示專用填寫說明，清楚區分正常工作、工作制以外工作和法定假日工作。",
                "大 E-CALL及普通 E-CALL 欄增加常駐提示：日工同一次工作不可同時計作出勤 1 日及大 E-CALL 1 次；普通 E-CALL 每次 HKD 400，可記錄完整出勤以外另行發生的召回。",
                "日工法定假日仍自動支付基本 1 倍；當日實際工作選擇出薪再加 1 倍，選擇補休則保留基本假日薪酬並增加補休。",
            ],
            "zh-Hans": [
                "每个出勤及休息日／法定假日字段按日工、例外月薪及 5／5.5／6 天制显示专用填写说明，清楚区分正常工作、工作制以外工作和法定假日工作。",
                "大 E-CALL及普通 E-CALL 字段增加常驻提示：日工同一次工作不可同时计作出勤 1 日及大 E-CALL 1 次；普通 E-CALL 每次 HKD 400，可记录完整出勤以外另行发生的召回。",
                "日工法定假日仍自动支付基本 1 倍；当日实际工作选择出薪再加 1 倍，选择补休则保留基本假日薪酬并增加补休。",
            ],
            "en": [
                "Attendance and rest-day/statutory-holiday fields show tailored guidance for daily workers, attendance-prorated monthly exceptions and each 5/5.5/6-day schedule.",
                "Permanent Large and ordinary E-CALL guidance prevents a daily worker's same event from being counted as both one attendance day and one Large E-CALL, while explaining the separate HKD 400 ordinary call-out.",
                "Daily statutory holidays retain the automatic base 1x entitlement; actual holiday work adds another 1x under Payroll or preserves base holiday pay and adds Comp Leave.",
            ],
        },
        "limitations": {
            "zh-Hant": ["日工核對基準不是已確認出勤；HR 仍須按簽署考勤 PDF 刪減休息及沒有上班的日數。E-CALL維持按 PDF 人工判斷，不建立事件日期推斷。"],
            "zh-Hans": ["日工核对基准不是已确认出勤；HR 仍须按签署考勤 PDF 删减休息及没有上班的日数。E-CALL维持按 PDF 人工判断，不建立事件日期推断。"],
            "en": ["A daily-worker baseline is not confirmed attendance. HR must remove rest and non-work days from the signed PDF. E-CALL remains a manual PDF judgement without inferred event dates."],
        },
    },
    {
        "version": "V0.3.2",
        "date": "2026-08-19",
        "title": {
            "zh-Hant": "工作日曆、每週工作制及例外月薪",
            "zh-Hans": "工作日历、每周工作制及例外月薪",
            "en": "Work calendars, workweeks and exceptional monthly pay",
        },
        "features": {
            "zh-Hant": [
                "月工及管理人員新增有效日期化的月薪計薪方式：預設為「標準月薪（整月計薪）」；合約明確約定有工作才上班等例外情況可選「按實際出勤曆日比例」，按月薪除以當月曆日再乘實際計薪出勤日數。",
                "任職記錄新增有效日期化的 5／5.5／6 天工作制；月底預估按員工當時的工作制計算，5.5 天制星期六上午按 0.5 日，並排除工作日曆內的法定假日。例外月薪不假設出勤，預估為 0。",
                "日工由入職日起自動獲付法定節假日正常日薪 1 倍；沒有上班亦會支付，當日實際上班選擇出薪時再加工作日薪 1 倍，選擇補休時保留假日薪酬並增加補休。",
                "資料選項的項目、MPF 及各下拉選項統一為唯讀列表與新增／編輯彈窗；引用員工數可查看具體員工，未設定資料獨立提示，不再把「未分配」當成正式選項。",
            ],
            "zh-Hans": [
                "月工及管理人员新增有效日期化的月薪计薪方式：默认为“标准月薪（整月计薪）”；合同明确约定有工作才上班等例外情况可选“按实际出勤历日比例”，按月薪除以当月历日再乘实际计薪出勤日数。",
                "任职记录新增有效日期化的 5／5.5／6 天工作制；月底预估按员工当时的工作制计算，5.5 天制星期六上午按 0.5 日，并排除工作日历内的法定假日。例外月薪不假设出勤，预估为 0。",
                "日工由入职日起自动获付法定节假日正常日薪 1 倍；没有上班也会支付，当日实际上班选择出薪时再加工作日薪 1 倍，选择补休时保留假日薪酬并增加补休。",
                "资料选项的项目、MPF 及各下拉选项统一为只读列表与新增／编辑弹窗；引用员工数可查看具体员工，未设置资料独立提示，不再把“未分配”当成正式选项。",
            ],
            "en": [
                "Monthly and management salary history adds an effective-dated pay method. Standard full-month salary remains the default; explicitly contracted on-demand exceptions can be prorated by actual paid calendar attendance days.",
                "Assignment history adds effective-dated 5/5.5/6-day workweeks. Month-end forecasts follow the employee's effective workweek, count Saturday morning as 0.5 under 5.5 days and exclude regional Work Calendar holidays; attendance-prorated exceptions forecast zero.",
                "Daily workers automatically receive one normal daily rate for every statutory holiday from employment start. Working that holiday adds another 1x under Payroll, or retains holiday pay and adds Comp Leave under Comp Leave.",
                "Projects, MPF schemes and reference choices use consistent read-only tables with add/edit dialogs. Current employee usage opens the actual employee list, while missing assignments are shown separately instead of as a synthetic Unassigned option.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "例外月薪考勤以「實際計薪出勤日數」記錄真正工作的曆日，星期六、星期日及法定假日直接計入且不另付星期日／法定節假日工作薪酬；年假、病假、無薪假及每日餐補／交通補貼沿用頁面常駐顯示的專用規則。",
                "低頻停用功能改名為「封存選項／恢復使用」並保留審計；封存只影響新資料選擇，不改動既有及歷史引用，只有從未引用的錯誤資料才可永久刪除。",
                "考勤月底預估下方常駐說明員工的 5／5.5／6 天工作制、法定假日來源及例外月薪預估規則；5 天制星期六、5.5 天制星期六下午、星期日及法定節假日真正工作統一使用出薪／補休，避免誤填為 OT。",
            ],
            "zh-Hans": [
                "例外月薪考勤以“实际计薪出勤日数”记录真正工作的日历日，星期六、星期日及法定假日直接计入且不另付星期日／法定节假日工作薪酬；年假、病假、无薪假及每日餐补／交通补贴沿用页面常驻显示的专用规则。",
                "低频停用功能改名为“封存选项／恢复使用”并保留审计；封存只影响新资料选择，不改动既有及历史引用，只有从未引用的错误资料才可永久删除。",
                "考勤月底预估下方常驻说明员工的 5／5.5／6 天工作制、法定假日来源及例外月薪预估规则；5 天制星期六、5.5 天制星期六下午、星期日及法定节假日真正工作统一使用出薪／补休，避免误填为 OT。",
            ],
            "en": [
                "Attendance-prorated monthly staff enter actual paid calendar attendance days. Saturday, Sunday and statutory-holiday work is included directly with no additional Sunday/statutory-holiday work payment; leave and daily allowance rules remain permanently visible.",
                "The low-frequency retirement action is now Archive/Restore with audit history. Archiving affects new choices only, while permanent deletion is limited to never-used mistakes.",
                "Forecast fields permanently explain the effective 5/5.5/6-day workweek, calendar-holiday source and zero-default exception rule. Work outside the workweek uses Payroll/Comp Leave, including 0.5 day for Saturday afternoon under a 5.5-day schedule, rather than OT.",
            ],
        },
        "limitations": {
            "zh-Hant": ["工作日曆由 HR 依官方資料維護，不在出糧時依賴網絡自動下載。"],
            "zh-Hans": ["工作日历由 HR 依官方资料维护，不在出粮时依赖网络自动下载。"],
            "en": ["HR maintains the work calendar from official sources; payroll does not depend on a live internet download."],
        },
    },
    {
        "version": "V0.3.1",
        "date": "2026-08-19",
        "title": {
            "zh-Hant": "資料補齊、考勤校驗與介面一致性",
            "zh-Hans": "资料补齐、考勤校验与界面一致性",
            "en": "Data completion, attendance validation and UI consistency",
        },
        "features": {
            "zh-Hant": [
                "員工總覽新增資料補齊工作台，直接按阻止出糧、影響假期計算、影響 MPF、附件或檔案完整度排列現有缺失資料；不另建任務系統，點擊缺失項可進入對應員工修正入口。",
                "考勤錄入新增四段即時輸入摘要及前後端日數校驗，集中顯示工作日、星期日／法定節假日、OT 與 E-CALL，並阻止負數、錯誤步進或超過考勤期間的日數保存。",
                "管理員新增唯讀系統運行狀態頁，顯示應用程式版本、資料庫版本、最近備份及最近還原驗證記錄；備份及還原仍沿用既有腳本。",
            ],
            "zh-Hans": [
                "员工总览新增资料补齐工作台，直接按阻止出粮、影响假期计算、影响 MPF、附件或档案完整度排列现有缺失资料；不另建任务系统，点击缺失项可进入对应员工修正入口。",
                "考勤录入新增四段即时输入摘要及前后端日数校验，集中显示工作日、星期日／法定节假日、OT 与 E-CALL，并阻止负数、错误步进或超过考勤期间的日数保存。",
                "管理员新增只读系统运行状态页，显示应用程序版本、数据库版本、最近备份及最近还原验证记录；备份及还原仍沿用既有脚本。",
            ],
            "en": [
                "Employee Overview adds a derived data-completion workbench grouped by payroll, leave, MPF and file-completeness impact, with direct links to the relevant employee correction entry and no parallel task system.",
                "Attendance Entry adds a live four-period summary and front/back-end day validation for working days, Sunday/statutory-holiday days, OT and E-CALL, blocking negative, malformed or period-exceeding values.",
                "Administrators gain a read-only System Status page for application/database versions and the latest backup and restore-verification records while existing scripts remain the only operational workflow.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "員工總覽只突出缺失項，資料完整及可出糧狀態合併為簡潔綠色標記，降低橫向信息噪音。",
                "假期總覽新增僅顯示需處理篩選，年假及補休統一顯示兩位小數；負數年假保留為真實超用狀態並以紅色提示核對。",
                "每月 Payroll 及離職 Payroll 的完整計算規則預設收起，頁面保留簡短常駐計算依據；月份輸入、表單提示及鍵盤焦點樣式在全站統一。",
            ],
            "zh-Hans": [
                "员工总览只突出缺失项，资料完整及可出粮状态合并为简洁绿色标记，降低横向信息噪音。",
                "假期总览新增仅显示需处理筛选，年假及补休统一显示两位小数；负数年假保留为真实超用状态并以红色提示核对。",
                "每月 Payroll 及离职 Payroll 的完整计算规则默认收起，页面保留简短常驻计算依据；月份输入、表单提示及键盘焦点样式在全站统一。",
            ],
            "en": [
                "Employee Overview emphasizes only missing items and collapses complete employee/payroll states into concise green markers.",
                "Leave Overview adds an attention-only filter, standardizes annual/comp-leave display to two decimals, and preserves genuine negative balances with an explicit overuse warning.",
                "Full Monthly and Departure Payroll rules are collapsed by default behind a persistent calculation-basis summary. Month inputs, form notes and keyboard focus styling are standardized across the app.",
            ],
        },
        "limitations": {
            "zh-Hant": ["本版本不加入 Payroll 關帳、解除關帳或出糧前差異報告。"],
            "zh-Hans": ["本版本不加入 Payroll 关账、解除关账或出粮前差异报告。"],
            "en": ["Payroll closing, reopening and pre-payroll difference reports are outside this release."],
        },
    },
    {
        "version": "V0.3.0",
        "date": "2026-08-18",
        "title": {
            "zh-Hant": "離職 Payroll、月份脈絡與薪酬來源統一",
            "zh-Hans": "离职 Payroll、月份脉络与薪酬来源统一",
            "en": "Departure Payroll, month context and unified pay sources",
        },
        "features": {
            "zh-Hant": [
                "「離職結算」更名為「離職 Payroll」；薪酬區三項功能統一為「每月 Payroll」、「每月 MPF 供款表」及「離職 Payroll」，並以置頂月份條清楚顯示目前處理月份。",
                "離職 Payroll 新增發薪單位篩選；預覽可看全部單位，正式匯出必須選定一個發薪單位，檔名亦保留單位代碼。",
                "離職 Payroll 自動承接最後工作日前生效的交通／餐補、特殊津貼、指定月份調整、考勤替班其他津貼及工傷醫療實銷；手動欄只保留無其他來源的例外款項。",
            ],
            "zh-Hans": [
                "“离职结算”更名为“离职 Payroll”；薪酬区三项功能统一为“每月 Payroll”、“每月 MPF 供款表”及“离职 Payroll”，并以置顶月份条清楚显示目前处理月份。",
                "离职 Payroll 新增发薪单位筛选；预览可看全部单位，正式导出必须选定一个发薪单位，文件名亦保留单位代码。",
                "离职 Payroll 自动承接最后工作日前生效的交通／餐补、特殊津贴、指定月份调整、考勤替班其他津贴及工伤医疗实销；手动栏只保留无其他来源的例外款项。",
            ],
            "en": [
                "Final Payment is renamed Departure Payroll. Payroll navigation consistently uses Monthly Payroll, Monthly MPF Contributions and Departure Payroll, each with a prominent sticky operating-month bar.",
                "Departure Payroll adds payroll-entity filtering. Preview may show all entities, while formal export requires one entity and carries its code in the filename.",
                "Departure Payroll automatically carries in transport/meal and special allowances effective through the last working day, month-specific adjustments, Attendance substitute-shift allowance and work-injury medical reimbursement. Manual fields remain for exceptions only.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "離職 Payroll 與每月 Payroll 採用相同補貼來源：交通／餐補按每日金額乘以最後工作日前的計薪曆日，特殊津貼按生效曆日佔整月比例計算。",
                "工傷醫療實銷增加離職實發金額，但不納入 MPF 有關入息；僱員 MPF 始終留在該員工同一工資行，不另產生 MPF 行。",
                "合約與附件的文件、狀態及操作欄改用固定欄寬與垂直置中，改善按鈕和內容對齊。",
            ],
            "zh-Hans": [
                "离职 Payroll 与每月 Payroll 采用相同补贴来源：交通／餐补按每日金额乘以最后工作日前的计薪日历日，特殊津贴按生效日历日占整月比例计算。",
                "工伤医疗实销增加离职实发金额，但不纳入 MPF 有关入息；雇员 MPF 始终保留在该员工同一工资行，不另产生 MPF 行。",
                "合约与附件的文件、状态及操作栏改用固定栏宽与垂直居中，改善按钮和内容对齐。",
            ],
            "en": [
                "Departure and Monthly Payroll now share allowance sources: transport/meal uses the daily rate times paid calendar days through departure, while special allowance is prorated by effective days over the full month.",
                "Work-injury medical reimbursement increases departure net pay but is excluded from MPF relevant income. Employee MPF remains on the same wage row and never creates a standalone line.",
                "The Contracts & Attachments table now uses stable column widths and vertically aligned file, status and action content.",
            ],
        },
        "limitations": {"zh-Hant": [], "zh-Hans": [], "en": []},
    },
    {
        "version": "V0.2.9",
        "date": "2026-08-17",
        "title": {
            "zh-Hant": "補貼日率、考勤搜尋與 Payroll 分行修正",
            "zh-Hans": "补贴日率、考勤搜索与 Payroll 分行修正",
            "en": "Daily allowance rates, attendance search and payroll-line fixes",
        },
        "features": {
            "zh-Hant": [
                "餐補及交通補貼改為按每日金額錄入，Payroll 按每日金額乘以計薪曆日；特殊津貼維持每月金額並按生效曆日比例計算。固定補貼目前只支持月工及 OFFICE，不支持日工。",
                "考勤錄入的員工選擇改為搜尋框，支持員工編號、英文姓名及繁簡體中文混合搜尋，並排除已離職員工。",
                "看板新增員工轉正提醒：管理／總部人員尚未轉正且試用期已到或將於 30 日內到期時顯示，按逾期、7 日內及 8–30 日分級提示；點擊員工直接進入任職狀態並開啟轉正視窗。",
            ],
            "zh-Hans": [
                "餐补及交通补贴改为按每日金额录入，Payroll 按每日金额乘以计薪日历日；特殊津贴维持每月金额并按生效日历日比例计算。固定补贴目前只支持月工及 OFFICE，不支持日工。",
                "考勤录入的员工选择改为搜索框，支持员工编号、英文姓名及繁简体中文混合搜索，并排除已离职员工。",
                "看板新增员工转正提醒：管理／总部人员尚未转正且试用期已到或将在 30 日内到期时显示，按逾期、7 日内及 8–30 日分级提示；点击员工直接进入任职状态并打开转正窗口。",
            ],
            "en": [
                "Meal and transport allowances are entered as daily rates and multiplied by paid calendar days. Special allowance remains monthly and is prorated by effective calendar days. Fixed allowances currently support Monthly and OFFICE only.",
                "Attendance Entry replaces the employee dropdown with search by employee number, English name, and mixed Traditional/Simplified Chinese, excluding departed employees.",
                "Dashboard adds confirmation reminders for active unconfirmed Management/OFFICE employees whose probation has ended or will end within 30 days, with overdue, 7-day and 8–30-day severity levels and a direct link to the confirmation editor.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "修正舊版免交考勤的月工／OFFICE 曾把日曆星期日當作實際工作；只清理完全符合舊版模式且沒有逐日工作記錄的資料，Payroll 同時設防，頁面常駐說明星期日／法定節假日日數只記錄真正額外工作。",
                "全局修正零金額分攤行可能單獨承載 MPF，造成同一員工看似兩次出糧；即使舊快照殘留出勤日數，匯出亦會移除沒有實際薪酬金額的空行，並把員工級 MPF 放在主要薪資行。Payroll XLSX 的月工、OFFICE 及日工 F4 均改以 YYYY-MM 顯示工資月份。",
                "考勤數字欄取得焦點後，滑鼠滾輪不再改變日數、時數、次數或金額；任職與薪酬的當前任職卡片改為突出顯示真正的入職日期，崗位生效日期仍保留在變更歷史。",
                "考勤詳情的退出按鈕移入固定月份列；『當前考勤月份』與具體年月在綠色列中央以相同大小的黃色字體醒目顯示，PDF 標題列不再重複佔用返回按鈕位置。",
            ],
            "zh-Hans": [
                "修正旧版免交考勤的月工／OFFICE 曾把日历星期日当作实际工作；只清理完全符合旧版模式且没有逐日工作记录的资料，Payroll 同时设防，页面常驻说明星期日／法定节假日日数只记录真正额外工作。",
                "全局修正零金额分摊行可能单独承载 MPF，造成同一员工看似两次出粮；即使旧快照残留出勤日数，导出也会移除没有实际薪酬金额的空行，并把员工级 MPF 放在主要薪资行。Payroll XLSX 的月工、OFFICE 及日工 F4 均改以 YYYY-MM 显示工资月份。",
                "考勤数字栏取得焦点后，鼠标滚轮不再改变日数、时数、次数或金额；任职与薪酬的当前任职卡片改为突出显示真正的入职日期，岗位生效日期仍保留在变更历史。",
                "考勤详情的退出按钮移入固定月份栏；“当前考勤月份”与具体年月在绿色栏中央以相同大小的黄色字体醒目显示，PDF 标题栏不再重复占用返回按钮位置。",
            ],
            "en": [
                "Fixes legacy attendance-exempt Monthly/OFFICE records that treated calendar Sundays as work. Only exact legacy patterns without dated work are cleared; Payroll also safeguards the rule and the UI states that special-day counts mean genuine extra work only.",
                "Globally removes zero-pay allocation rows that could carry MPF separately and make one employee appear twice, including legacy rows with residual attendance counts. Employee-level MPF stays on the principal salary row, and F4 shows the payroll month as YYYY-MM in all Daily, Monthly and OFFICE XLSX exports.",
                "Mouse-wheel scrolling no longer changes focused Attendance number fields. The current Employment card emphasizes the true employment start date while assignment effective dates remain in change history.",
                "Moves Exit Detail into the sticky month bar, centers the current-attendance label and specific month in the same large highlighted-yellow type, and leaves the PDF heading dedicated to file and batch details.",
            ],
        },
        "limitations": {"zh-Hant": [], "zh-Hans": [], "en": []},
    },
    {
        "version": "V0.2.8",
        "date": "2026-08-17",
        "title": {
            "zh-Hant": "工傷、離職結算與月度薪酬規則",
            "zh-Hans": "工伤、离职结算与月度薪酬规则",
            "en": "Work injury, final payment and monthly payroll rules",
        },
        "features": {
            "zh-Hant": [
                "「假期管理」升級為「假期與工傷」，左欄並列假期管理與工傷管理；工傷管理成為工傷期間、是否按工傷 4/5 計薪或全薪、免考勤及憑證的唯一維護入口，員工檔案只保留摘要、歷史與前往管理的連結。",
                "工傷記錄可按月份登記復診／醫療開支實銷；金額匯入工傷補償金／醫療開支欄（日工 AM；月工／OFFICE AN）並增加實發金額，但不納入 MPF 有關入息。",
                "考勤實際項目行新增「替班其他津貼」，以常駐提示限定為代替工傷等同事當值的額外津貼，匯入 Other Payment；固定補貼卡片改名「固定補貼」，補發、追扣及一次性更正則集中到每月 Payroll 的單一入口。",
                "離職月份以已確認的 Final Payment 作為唯一工資來源；每月 MPF 同月保留離職員工並採用 Final Payment 的 MPF 金額，避免普通 Payroll 與離職結算重複出糧或重複供款。",
            ],
            "zh-Hans": [
                "“假期管理”升级为“假期与工伤”，左栏并列假期管理与工伤管理；工伤管理成为工伤期间、是否按工伤 4/5 计薪或全薪、免考勤及凭证的唯一维护入口，员工档案只保留摘要、历史与前往管理的链接。",
                "工伤记录可按月份登记复诊／医疗开支实销；金额导入工伤补偿金／医疗开支栏（日工 AM；月工／OFFICE AN）并增加实发金额，但不纳入 MPF 有关入息。",
                "考勤实际项目行新增“替班其他津贴”，以常驻提示限定为代替工伤等同事当值的额外津贴，导入 Other Payment；固定补贴卡片改名“固定补贴”，补发、追扣及一次性更正集中到每月 Payroll 的单一入口。",
                "离职月份以已确认的 Final Payment 作为唯一工资来源；每月 MPF 同月保留离职员工并采用 Final Payment 的 MPF 金额，避免普通 Payroll 与离职结算重复出粮或重复供款。",
            ],
            "en": [
                "Leave Management becomes Leave & Work Injury with peer leave and injury cards. Work Injury Management is the sole maintenance entry for dated periods, 4/5 work-injury pay or full pay, attendance exemption and evidence; the employee profile keeps only a summary, history and management link.",
                "Monthly follow-up and medical reimbursement can be recorded against a work injury. It exports to Work Injury Compensation / Medical Expenses (AM for Daily; AN for Monthly and OFFICE), increases net pay and is excluded from MPF relevant income.",
                "Actual Attendance project rows add a clearly scoped substitute-shift other allowance that exports to Other Payment. Fixed allowances are renamed accordingly, while arrears, clawbacks and one-off wage corrections move to one employee/month entry in Monthly Payroll.",
                "Confirmed Final Payment is the sole wage source in the departure month. Monthly MPF retains the departing employee in that month using the Final Payment contribution, preventing duplicate wages or contributions from ordinary Payroll.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "考勤上傳批次改為只管理 PDF，不再綁定整批月份；每份 PDF 在詳情頁獨立確認月份，四段日期、假期聯動及前月資料會隨月份刷新。已保存文件可直接『重新預覽』並保存月份更正，無需重新上傳。",
                "離職年度年假按含頭尾兩日的當年在職日數除以 365／366 自動折算；超用先抵扣其他可用年假，仍不足部分在 Final Payment 追扣。年假補薪日薪率改為前 12 個月工資合計除以 365，並顯示找到的 Payroll 月數及 HR 核實提示。",
                "假期與工傷新增姓名／員工編號搜尋，支援中文繁簡體及英文姓名；考勤聯動框分別說明日工的實際出勤日數是唯一計薪依據、不會再因無薪假重複扣薪，而月工／OFFICE 的無薪假只按假期記錄扣減一次。",
                "工傷、離職結算、MPF、病假／無薪假及各類補貼的計算規則在相應頁面常駐顯示；工傷計薪基礎預填合約底薪，並提示 HR 按意外發生時每月收入核實。",
                "工傷計薪方式、每月醫療實銷、離職年假折算及 Payroll 結果均保留結構化資料與審計軌跡；資料庫升級採加法式欄位，不覆蓋既有員工記錄。",
            ],
            "zh-Hans": [
                "考勤上传批次改为只管理 PDF，不再绑定整批月份；每份 PDF 在详情页独立确认月份，四段日期、假期联动及前月资料会随月份刷新。已保存文件可直接“重新预览”并保存月份更正，无需重新上传。",
                "离职年度年假按含头尾两日的当年在职日数除以 365／366 自动折算；超用先抵扣其他可用年假，仍不足部分在 Final Payment 追扣。年假补薪日薪率改为前 12 个月工资合计除以 365，并显示找到的 Payroll 月数及 HR 核实提示。",
                "假期与工伤新增姓名／员工编号搜索，支持中文繁简体及英文姓名；考勤联动框分别说明日工的实际出勤日数是唯一计薪依据、不会再因无薪假重复扣薪，而月工／OFFICE 的无薪假只按假期记录扣减一次。",
                "工伤、离职结算、MPF、病假／无薪假及各类补贴的计算规则在相应页面常驻显示；工伤计薪基础预填合同底薪，并提示 HR 按意外发生时每月收入核实。",
                "工伤计薪方式、每月医疗实销、离职年假折算及 Payroll 结果均保留结构化资料与审计轨迹；数据库升级采用加法式栏位，不覆盖既有员工记录。",
            ],
            "en": [
                "Attendance upload batches now group PDFs without imposing one month on the whole batch. Each PDF confirms its own month, refreshing all four periods, linked leave and prior-month context. Saved files can be re-previewed and corrected without re-uploading.",
                "Departure-year annual leave is prorated by inclusive employment days over 365/366. Overuse first offsets other leave and any remainder is deducted in Final Payment. Leave pay uses the verified previous-12-month wage total divided by 365, with the Payroll-month count and HR verification shown.",
                "Leave & Work Injury adds Simplified/Traditional Chinese, English-name and employee-number search. Linked Attendance notes explain that a daily worker's entered attendance days are the sole pay basis and are not reduced again for unpaid leave, while Monthly/OFFICE unpaid leave is deducted once from leave records.",
                "Work-injury, Final Payment, MPF, sick/unpaid leave and allowance rules remain visible in their owning pages. Work-injury earnings prefill contract salary and remind HR to verify monthly earnings at the accident date.",
                "Work-injury pay mode, monthly medical reimbursement, departure leave proration and Payroll results retain structured data and audit history. Additive schema upgrades preserve existing employee records.",
            ],
        },
        "limitations": {"zh-Hant": [], "zh-Hans": [], "en": []},
    },
    {
        "version": "V0.2.7",
        "date": "2026-08-14",
        "title": {
            "zh-Hant": "發薪單位、薪酬計算與員工資料時間線",
            "zh-Hans": "发薪单位、薪酬计算与员工资料时间线",
            "en": "Payroll entities, payroll calculation and employee-record timelines",
        },
        "features": {
            "zh-Hant": [
                "每月 Payroll 新增發薪單位篩選；正式導出限定一個發薪單位，未設定者不會混入任何公司工資表，導出檔名同步標示發薪單位。",
                "個人資料新增有生效日期的銀行賬戶當前狀態與變更歷史，可更正、撤回、後補或替換附件；撤回後會自動恢復使用上一筆仍有效的銀行資料。",
                "三寶改為同一來源下的身份證、平安卡及工人註冊證三項結構化資料；平安卡與工人註冊證均可記錄到期日並納入看板提醒。",
                "VISA 介面統一稱為「簽證／工作許可」；工作許可名稱與其他簽證類型一樣由資料選項維護，HR 可按實際證件名稱新增選項。",
            ],
            "zh-Hans": [
                "每月 Payroll 新增发薪单位筛选；正式导出限定一个发薪单位，未设置者不会混入任何公司工资表，导出文件名同步标示发薪单位。",
                "个人资料新增有生效日期的银行账户当前状态与变更历史，可更正、撤回、后补或替换附件；撤回后会自动恢复使用上一笔仍有效的银行资料。",
                "三宝改为同一来源下的身份证、平安卡及工人注册证三项结构化资料；平安卡与工人注册证均可记录到期日并纳入看板提醒。",
                "VISA 界面统一称为“签证／工作许可”；工作许可名称与其他签证类型一样由资料选项维护，HR 可按实际证件名称新增选项。",
            ],
            "en": [
                "Monthly Payroll filters by payroll entity. A formal export contains exactly one entity, excludes employees with no entity, and includes the entity code in the filename.",
                "Personal Data now has effective-dated current bank details and history with correction, withdrawal, later evidence upload and attachment replacement. Withdrawing a record restores the previous effective bank details.",
                "Three Treasures is one source for structured identity, safety-card and worker-registration facts. Safety cards and worker registrations both support expiry dates and Dashboard reminders.",
                "VISA is renamed Visa / Work Permit. HR can maintain actual work-permit and visa names through Data Options.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "修正月工／OFFICE 的曆日薪金率與計薪曆日：曆日薪金率固定按月薪除以當月曆日，計薪曆日按實際有薪日計算，預估工作日不再重複增加月薪分母。",
                "上月 OT、E-CALL 及星期日／法定節假日出薪改用各自欄位對比原預估，避免相同款項再次落入少付／多付薪金；日工與月工 Payroll 回歸測試均覆蓋此規則。",
                "病假薪酬重新核對並加入回歸測試：通過試用期後，同一曆月首 1 日全薪，其後日數按 4/5；未通過試用期由首日起按 4/5。年假維持全薪，無薪假按無出勤扣薪。",
                "修正新增工傷記錄時因可選欄位處理不完整而出現的 500 錯誤；工傷期間仍由首日起按 HR 核實月入的 4/5 計薪。",
                "看板到期提示按已到期、30 日內及 31–60 日分為紅、橙、黃三級，已到期的 VISA、平安卡及工人註冊證更容易辨認。",
                "員工檔案統一採用任職與薪酬的『當前狀態＋變更歷史』模式：個人資料以基本、聯絡及銀行卡片顯示，普通資料按『編輯個人資料』開啟大視窗，不再預設鋪開表單。",
                "證件與資歷上方按類別顯示全部有效記錄，下方統一保留新增、更正、作廢與憑證歷史；學歷背景及工作許可要求亦歸入此頁。轉正／離職改名任職狀態，離職表單改為按鈕開啟，並新增任職期間歷史。",
                "考勤詳情的應收總數改為清楚顯示『應收＝未收＋已收』；三個統計預設不展開，點擊後才顯示員工、Payroll 組別及所選月份內曾隸屬的項目。",
                "考勤、每月 Payroll 及每月 MPF 共用同一操作月份並以醒目固定列顯示完整年月；四段考勤改用實際年月日期，不再使用模糊的本月／上月標題。歷史月份的整體、已選及單人 Payroll 導出均嚴格沿用畫面所選月份。",
                "合約與附件改為文件總覽及下載中心：CV／其他一般附件可直接維護；銀行、證件、任職薪酬、假期／工傷及考勤附件返回所屬專項模組管理。生成雇傭合約移至任職與薪酬，避免同一資料出現兩套修改入口。",
            ],
            "zh-Hans": [
                "修正月工／OFFICE 的日历日薪金率与计薪日历日：日历日薪金率固定按月薪除以当月日历日，计薪日历日按实际有薪日计算，预计工作日不再重复增加月薪分母。",
                "上月 OT、E-CALL 及星期日／法定节假日出薪改用各自栏位对比原预计，避免相同款项再次落入少付／多付薪金；日工与月工 Payroll 回归测试均覆盖此规则。",
                "病假薪酬重新核对并加入回归测试：通过试用期后，同一日历月首 1 日全薪，其后日数按 4/5；未通过试用期由首日起按 4/5。年假维持全薪，无薪假按无出勤扣薪。",
                "修正新增工伤记录时因可选栏位处理不完整而出现的 500 错误；工伤期间仍由首日起按 HR 核实月入的 4/5 计薪。",
                "看板到期提示按已到期、30 日内及 31–60 日分为红、橙、黄三级，已到期的 VISA、平安卡及工人注册证更容易辨认。",
                "员工档案统一采用任职与薪酬的“当前状态＋变更历史”模式：个人资料以基本、联络及银行卡片显示，普通资料按“编辑个人资料”打开大窗口，不再默认铺开表单。",
                "证件与资历上方按类别显示全部有效记录，下方统一保留新增、更正、作废与凭证历史；学历背景及工作许可要求亦归入此页。转正／离职改名任职状态，离职表单改为按钮打开，并新增任职期间历史。",
                "考勤详情的应收总数改为清楚显示“应收＝未收＋已收”；三个统计默认不展开，点击后才显示员工、Payroll 组别及所选月份内曾隶属的项目。",
                "考勤、每月 Payroll 及每月 MPF 共用同一操作月份并以醒目固定栏显示完整年月；四段考勤改用实际年月日期，不再使用模糊的本月／上月标题。历史月份的整体、已选及单人 Payroll 导出均严格沿用画面所选月份。",
                "合约与附件改为文件总览及下载中心：CV／其他一般附件可直接维护；银行、证件、任职薪酬、假期／工伤及考勤附件返回所属专项模块管理。生成雇佣合同移至任职与薪酬，避免同一资料出现两套修改入口。",
            ],
            "en": [
                "Monthly/OFFICE calendar-day rates and paid calendar days are corrected: the rate is monthly salary divided by calendar days in the month, paid days follow actual paid days, and forecast workdays no longer inflate the divisor.",
                "Prior OT, E-CALL and Sunday/statutory-holiday pay are compared through their dedicated forecast fields instead of being duplicated under overpayment or underpayment; daily and monthly regression cases cover the rule.",
                "Sick pay is rechecked and regression-tested: after probation the first aggregate day in a calendar month is fully paid and later days pay at 4/5; before probation every sick day pays at 4/5. Annual leave remains paid and unpaid leave is treated as no attendance.",
                "Creating a work-injury record no longer fails when optional fields are left blank. Covered days continue to pay at 4/5 of HR-verified accident-time monthly earnings from day one.",
                "Dashboard expiry alerts use red for expired, orange for 30 days or less and yellow for 31–60 days, covering VISA, safety cards and worker registrations.",
                "Employee tabs now follow the same current-state then change-history pattern as Employment & Salary. Personal details use basic, contact and bank cards, and ordinary edits open in a large dialog instead of an always-open form.",
                "Credentials shows every active record by category above a unified correction, void and evidence history. Education and work-permit requirements move there. Confirmation / Termination is renamed Employment Status, with button-opened forms and employment-period history.",
                "Attendance due is explicitly defined as missing plus received. All three totals start collapsed and reveal employee, Payroll group and every project held during the selected month only when clicked.",
                "Attendance, Monthly Payroll and Monthly MPF share one operating month with a prominent sticky full-month display. Four-part periods use exact dates, while every historical bulk, selected or single-employee Payroll export preserves the month selected on screen.",
                "Contracts & Attachments is now the document overview and download centre. CV/other general files remain editable there, while bank, credential, employment/pay, leave/work-injury and attendance evidence returns to its owning module. Contract generation moves to Employment & Salary.",
            ],
        },
        "limitations": {"zh-Hant": [], "zh-Hans": [], "en": []},
    },
    {
        "version": "V0.2.6",
        "date": "2026-08-13",
        "title": {
            "zh-Hant": "假期、星期日／法定節假日、工傷與補貼薪酬聯動",
            "zh-Hans": "假期、星期日／法定节假日、工伤与补贴薪酬联动",
            "en": "Leave, Sunday/statutory-holiday, work-injury and allowance payroll integration",
        },
        "features": {
            "zh-Hant": [
                "導覽重新按 HR 工作目的整理：工作總覽改為看板、員工管理改為員工總覽、年假管理改為假期管理、考勤管理改為考勤錄入；薪酬及資料匯出亦重新分組，每月 MPF 供款表移至每月 Payroll 下方。",
                "假期管理統一處理年假、病假及無薪假，支援 0.5 日單位、日期範圍、憑證與員工假期詳情；考勤頁只在當月確有記錄時顯示唯讀假期資料，任何改動必須返回假期管理完成。",
                "補休與普通請假分帳：補休不能在新增請假中直接建立，只由考勤錄入的休息日／法定假日工作選擇「補休」後自動產生，永久保留來源日期及時間線且暫不設到期日；放年假時優先扣除補休，再扣 2023 年及以前結餘，最後扣最早到期的 2024 年起結餘。",
                "考勤錄入按 Payroll 組別顯示不同欄位：日工錄入普通計薪工作日，月工及 OFFICE 以合約月薪為基礎而不再要求普通出勤日數；三組均以實際日期記錄休息日／法定假日工作，並整份考勤統一選擇「出薪」或「補休」。",
                "月工與 OFFICE 採曆日月薪；平日下班後 OT 按時薪 1.5 倍，星期日／法定節假日如選擇出薪按日薪率額外 1 倍，如選擇補休則不另付當日工資。日工同樣可選出薪 1 倍或只增加補休。",
                "病假按同一曆月累計：只有已通過試用期的員工享有首 1 日全薪，其後日數按 4/5 計薪；未通過試用期者由首日起按 4/5。月工與日工均適用，病假憑證可後補且不阻止 Payroll 匯出。",
                "工傷改為員工的有效日期記錄而不是在職狀態：合約底薪只作預填，HR 應按意外發生時每月收入核實及調整；工傷期由首日起按 4/5 計薪並豁免相關考勤，整月工傷時無需提交該月考勤。計算規則及勞工處提示會常駐顯示。",
                "任職與薪酬新增餐補、交通補貼及特殊津貼時間線，支援生效／結束日期、幣種、跨幣種匯率、附件、更正及撤回；餐補與交通補貼匯入 Traffic Allowance / Meal Allowance，特殊津貼保留匯入 Bonus / Fixed Allowance。",
                "指定月份的補發、扣減及一次性調整改名為「指定月份調整」，繼續匯入 Other Payment，與長期固定補貼清楚分工。",
            ],
            "zh-Hans": [
                "导航重新按 HR 工作目的整理：工作总览改为看板、员工管理改为员工总览、年假管理改为假期管理、考勤管理改为考勤录入；薪酬及资料导出亦重新分组，每月 MPF 供款表移至每月 Payroll 下方。",
                "假期管理统一处理年假、病假及无薪假，支持 0.5 日单位、日期范围、凭证与员工假期详情；考勤页只在当月确有记录时显示只读假期资料，任何改动必须返回假期管理完成。",
                "补休与普通请假分账：补休不能在新增请假中直接建立，只由考勤录入的休息日／法定假日工作选择“补休”后自动产生，永久保留来源日期及时间线且暂不设到期日；放年假时优先扣除补休，再扣 2023 年及以前结余，最后扣最早到期的 2024 年起结余。",
                "考勤录入按 Payroll 组别显示不同栏位：日工录入普通计薪工作日，月工及 OFFICE 以合约月薪为基础而不再要求普通出勤日数；三组均以实际日期记录休息日／法定假日工作，并整份考勤统一选择“出薪”或“补休”。",
                "月工与 OFFICE 采用日历日月薪；平日下班后 OT 按时薪 1.5 倍，星期日／法定节假日如选择出薪按日薪率额外 1 倍，如选择补休则不另付当日工资。日工同样可选出薪 1 倍或只增加补休。",
                "病假按同一日历月累计：只有已通过试用期的员工享有首 1 日全薪，其后日数按 4/5 计薪；未通过试用期者由首日起按 4/5。月工与日工均适用，病假凭证可后补且不阻止 Payroll 导出。",
                "工伤改为员工的有效日期记录而不是在职状态：合约底薪只作预填，HR 应按意外发生时每月收入核实及调整；工伤期由首日起按 4/5 计薪并豁免相关考勤，整月工伤时无需提交该月考勤。计算规则及劳工处提示会常驻显示。",
                "任职与薪酬新增餐补、交通补贴及特殊津贴时间线，支持生效／结束日期、币种、跨币种汇率、附件、更正及撤回；餐补与交通补贴导入 Traffic Allowance / Meal Allowance，特殊津贴保留导入 Bonus / Fixed Allowance。",
                "指定月份的补发、扣减及一次性调整改名为“指定月份调整”，继续导入 Other Payment，与长期固定补贴清楚分工。",
            ],
            "en": [
                "Navigation is reorganized around HR tasks: Dashboard, Employee Overview, Leave Management, Attendance Entry, Payroll Analytics & Export, and Data Settings & Export; the Monthly MPF Contribution Report now sits directly below Monthly Payroll.",
                "Leave Management handles annual, sick and unpaid leave in 0.5-day units with date ranges, evidence and employee-focused detail. Attendance shows linked leave only when the selected month has records and keeps it read-only.",
                "Comp leave is separate from leave entry. It is created only when dated rest-day/statutory-holiday attendance is treated as Comp Leave, retains its source timeline without expiry, and is consumed before legacy and regular annual-leave balances.",
                "Attendance fields now follow Payroll group: daily workers enter ordinary paid workdays, while Monthly and OFFICE staff use calendar-based contract salary. Every group records actual special-work dates and applies one Payroll/Comp Leave treatment to the attendance record.",
                "Weekday overtime for Monthly and OFFICE staff remains 1.5x hourly rate. Paid Sunday/statutory-holiday work adds 1x daily rate; selecting Comp Leave adds no extra payment. Daily workers follow the same Payroll-or-Comp-Leave choice.",
                "After probation, sick leave pays the first aggregate day in each calendar month in full and later days at 4/5; before probation it pays 4/5 from day one. This applies to monthly and daily staff, and missing evidence remains a visible non-blocking warning.",
                "Work injury is an effective-dated record rather than an employment status. Contract salary is only a prefill for HR-verified accident-time monthly earnings; covered days pay at 4/5 from day one and are exempt from attendance, including full-month exemption.",
                "Employment & Salary now includes effective-dated meal, transport and special allowances with currency conversion, evidence, correction and withdrawal history. Meal/transport map to Traffic Allowance / Meal Allowance; special allowance remains under Bonus / Fixed Allowance.",
                "One-off arrears, deductions and adjustments are renamed Month-specific adjustments and continue to map to Other Payment, keeping them separate from fixed allowances.",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "員工詳情移除重複的頂部快捷鍵；附件改為「合約與附件」，上傳、生成合約及附件打包集中在同一頁，並新增與獨立假期管理互相聯動的個人假期頁。",
                "當前任職、當前薪酬及 MPF、當前補貼各自在卡片內提供新增／調整按鈕，改用較大的彈窗填寫，避免原有窄小下拉區域。",
                "假期總覽可按年份、狀態、項目及 Payroll 組別篩選；點擊員工後進入單一員工詳情，再以返回按鈕回到原篩選結果。",
                "考勤選定員工後直接顯示 Payroll 類別及該組別的簡明計薪規則，日工、月工與 OFFICE 的輸入欄位和預估提示會同步切換。",
                "考勤員工欄合併為「請選擇員工」，文件名提示置於同一欄內；星期日／法定節假日錄入改為先填整日總數，再逐日使用日期選擇器指定日期，暫不選擇上午／下午。只有實際日數大於 0 時才顯示整份考勤的出薪／補休選項。",
                "本月 21 日至月底預估及上月 21 日至月底原預估均可填預估工作日出勤日數及星期日／法定節假日預估出勤日數，不設 OT 或 E-CALL。上月原預估優先帶入上月已保存數值，沒有上月記錄時預設為 0。",
                "四段考勤的固定資料列移除沒有必要的刪除叉號；如涉及多個項目，仍可使用新增項目分列填寫。",
                "考勤頁與 Payroll 計算規則均常駐顯示病假、工傷、星期日／法定節假日出薪／補休及 OT 規則，減少 HR 需要憑記憶判斷。",
                "月工、OFFICE、日工三張 Payroll 工作表更新月薪標準、曆日薪金率、計薪日及星期日／法定節假日欄名；病假／工傷共用原有區塊，以合計日數、平均計薪率及合計金額輸出。",
                "Payroll 公式同步納入星期日／法定節假日出薪、固定補貼、病假、工傷及指定月份調整，並保留 Excel 公式供覆核。",
                "假期總覽恢復多欄員工卡片排列；基礎資料改名為資料選項。補貼不再另設時間線，而是與任職、薪酬及 MPF 一同按生效日期列入變更歷史。",
                "補貼新增及更正視窗加入結束日期可留空提示；記錄彈窗放寬並支援由邊緣或四角縮放，內部表單隨視窗尺寸自動調整。",
                "資料模型與加法式資料庫遷移已擴充假期類別、補休來源與扣帳、星期日／法定節假日日期、工傷期間、固定補貼及 Payroll 計算快照，保留既有資料和審計軌跡；目前考勤介面只接受整日星期日／法定節假日。",
                "上月 21 日至月底原預估提供上月考勤 PDF 新視窗對照；未找到時按鍵會自動置灰並明確提示。全系統表單欄位改為頂部對齊，統一提示文字的字體、顏色、行距及位置，避免有提示的輸入框被推移。",
            ],
            "zh-Hans": [
                "员工详情移除重复的顶部快捷键；附件改为“合约与附件”，上传、生成合约及附件打包集中在同一页，并新增与独立假期管理互相联动的个人假期页。",
                "当前任职、当前薪酬及 MPF、当前补贴各自在卡片内提供新增／调整按钮，改用较大的弹窗填写，避免原有窄小下拉区域。",
                "假期总览可按年份、状态、项目及 Payroll 组别筛选；点击员工后进入单一员工详情，再以返回按钮回到原筛选结果。",
                "考勤选定员工后直接显示 Payroll 类别及该组别的简明计薪规则，日工、月工与 OFFICE 的输入栏位和预计提示会同步切换。",
                "考勤员工栏合并为“请选择员工”，文件名提示置于同一栏内；星期日／法定节假日录入改为先填整日总数，再逐日使用日期选择器指定日期，暂不选择上午／下午。只有实际日数大于 0 时才显示整份考勤的出薪／补休选项。",
                "本月 21 日至月底预计及上月 21 日至月底原预计均可填预计工作日出勤日数及星期日／法定节假日预计出勤日数，不设 OT 或 E-CALL。上月原预计优先带入上月已保存数值，没有上月记录时预设为 0。",
                "四段考勤的固定资料列移除没有必要的删除叉号；如涉及多个项目，仍可使用新增项目分列填写。",
                "考勤页与 Payroll 计算规则均常驻显示病假、工伤、星期日／法定节假日出薪／补休及 OT 规则，减少 HR 需要凭记忆判断。",
                "月工、OFFICE、日工三张 Payroll 工作表更新月薪标准、日历日薪金率、计薪日及星期日／法定节假日栏名；病假／工伤共用原有区块，以合计天数、平均计薪率及合计金额输出。",
                "Payroll 公式同步纳入星期日／法定节假日出薪、固定补贴、病假、工伤及指定月份调整，并保留 Excel 公式供复核。",
                "假期总览恢复多栏员工卡片排列；基础资料改名为资料选项。补贴不再另设时间线，而是与任职、薪酬及 MPF 一同按生效日期列入变更历史。",
                "补贴新增及更正窗口加入结束日期可留空提示；记录弹窗放宽并支持由边缘或四角缩放，内部表单随窗口尺寸自动调整。",
                "资料模型与加法式数据库迁移已扩充假期类别、补休来源与扣账、星期日／法定节假日日期、工伤期间、固定补贴及 Payroll 计算快照，保留既有资料和审计轨迹；目前考勤界面只接受整日星期日／法定节假日。",
                "上月 21 日至月底原预计提供上月考勤 PDF 新窗口对照；未找到时按钮会自动置灰并明确提示。全系统表单栏位改为顶部对齐，统一提示文字的字体、颜色、行距及位置，避免有提示的输入框被推移。",
            ],
            "en": [
                "Employee details remove duplicate top actions and centralize uploads, contract generation and bundling under Contracts & Attachments, with a linked personal Leave page.",
                "Current Assignment, Salary & MPF and Allowances use in-card actions and larger record-entry dialogs.",
                "Leave Overview filters by year, status, project and Payroll group, then opens a focused employee view with a return action.",
                "Selecting an employee in Attendance now shows the Payroll group and a concise rule for that group; daily, monthly and OFFICE inputs and forecast guidance switch together.",
                "The Attendance employee field is consolidated as Select employee with the filename reminder inside the same field. Sunday/statutory-holiday actual work is entered as whole days first and then dated, with AM/PM selection temporarily removed. Payroll/Comp Leave appears only when actual days exceed zero.",
                "Current 21-end and original prior 21-end forecasts both accept forecast workdays and forecast Sunday/statutory-holiday days, without OT or E-CALL. The original prior forecast comes from the saved prior-month forecast and defaults to zero when none exists.",
                "The unnecessary delete crosses are removed from the four fixed attendance sections; Add project remains available when work must be split across projects.",
                "Attendance and Payroll pages keep sick-leave, work-injury, Sunday/statutory-holiday and overtime rules visible for HR review.",
                "All three Payroll sheets use clearer salary basis, calendar/paid-day and Sunday/statutory-holiday labels. Sick leave/work injury share the established block using combined days, average rate and total amount.",
                "Payroll formulas cover Sunday/statutory-holiday pay, fixed allowances, sick leave, work injury and month-specific adjustments while remaining visible in Excel for review.",
                "Leave Overview restores a dense multi-column employee-card grid; Reference Data is renamed Data Options. Allowances now join Assignment, Salary and MPF in one effective-dated Change History.",
                "Allowance add/correct dialogs mark End date as optional. Record dialogs are wider and resizable from their edges or corners, with forms adapting to the selected size.",
                "Additive schema migration extends leave, comp-credit allocation, dated Sunday/statutory-holiday work, work-injury periods, allowances and Payroll snapshots without replacing existing HR records or audit history; Attendance currently accepts whole-day Sunday/statutory-holiday entries only.",
                "The original prior-month 21-end forecast now opens the previous attendance PDF in a new window, or shows a disabled action and a clear not-found note. Forms across the system use top-aligned controls and consistent hint typography, colour, spacing and placement so helper text no longer shifts adjacent inputs.",
            ],
        },
        "limitations": {
            "zh-Hant": ["兼職考勤及薪酬規則尚未實作，待有實際安排後另行確認"],
            "zh-Hans": ["兼职考勤及薪酬规则尚未实现，待有实际安排后另行确认"],
            "en": ["Part-time attendance and payroll remain deferred until an actual arrangement is confirmed"],
        },
    },
    {
        "version": "V0.2.5",
        "date": "2026-08-12",
        "title": {
            "zh-Hant": "員工總表 MPF 資料狀態",
            "zh-Hans": "员工总表 MPF 资料状态",
            "en": "MPF data status in the employee register",
        },
        "features": {
            "zh-Hant": [
                "員工總表的員工檔案欄顯示 MPF 資料已填寫或未填寫，並可直接開啟任職與薪酬頁處理",
            ],
            "zh-Hans": [
                "员工总表的员工档案栏显示 MPF 资料已填写或未填写，并可直接打开任职与薪酬页处理",
            ],
            "en": [
                "The Employee File column shows whether MPF details are entered and links directly to Employment & Salary",
            ],
        },
        "improvements": {
            "zh-Hant": ["MPF 狀態按所選月份的有效記錄判定，離職後月份不再顯示"],
            "zh-Hans": ["MPF 状态按所选月份的有效记录判定，离职后月份不再显示"],
            "en": ["MPF status follows the selected month's effective record and is hidden after employment ends"],
        },
        "limitations": {"zh-Hant": [], "zh-Hans": [], "en": []},
    },
    {
        "version": "V0.2.4",
        "date": "2026-08-12",
        "title": {
            "zh-Hant": "統一任職、薪酬及 MPF 變更歷史",
            "zh-Hans": "统一任职、薪酬及 MPF 变更历史",
            "en": "Unified assignment, salary and MPF change history",
        },
        "features": {
            "zh-Hant": [
                "任職、薪酬及 MPF 按生效日期合併為一張變更歷史表",
                "每筆記錄直接顯示生效內容、憑證、錄入或最近更正人及操作日期",
            ],
            "zh-Hans": [
                "任职、薪酬及 MPF 按生效日期合并为一张变更历史表",
                "每笔记录直接显示生效内容、凭证、录入或最近更正人及操作日期",
            ],
            "en": [
                "Assignment, salary and MPF now share one effective-date ordered change history",
                "Each record shows its effective details, evidence, latest editor and operation date",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "更正與撤回審計附在原業務記錄下方，不再重複顯示為另一條平級時間線",
                "員工詳情首頁移除重複的完整時間線，當前資料與各頁籤記錄分工更清楚",
            ],
            "zh-Hans": [
                "更正与撤回审计附在原业务记录下方，不再重复显示为另一条平级时间线",
                "员工详情首页移除重复的完整时间线，当前资料与各页签记录分工更清楚",
            ],
            "en": [
                "Correction and withdrawal audit details stay beneath the originating business record instead of appearing as a duplicate timeline event",
                "The duplicate full timeline was removed from the employee overview so current data and domain records have clearer roles",
            ],
        },
        "limitations": {"zh-Hant": [], "zh-Hans": [], "en": []},
    },
    {
        "version": "V0.2.3",
        "date": "2026-08-12",
        "title": {
            "zh-Hant": "MPF 計劃記錄與每月供款表",
            "zh-Hans": "MPF 计划记录与每月供款表",
            "en": "MPF scheme records and monthly contribution reports",
        },
        "features": {
            "zh-Hant": [
                "員工檔案顯示當前 MPF 計劃、Member Account No. 及生效日期；轉換計劃時保留舊記錄",
                "基礎資料可維護 MPF 計劃名稱、僱主帳戶號碼及工資組別編號",
                "MPF 供款表按計劃下載 XLSX，全部計劃下載 ZIP；供款金額直接採用同月 Payroll 結果",
            ],
            "zh-Hans": [
                "员工档案显示当前 MPF 计划、Member Account No. 及生效日期；转换计划时保留旧记录",
                "基础资料可维护 MPF 计划名称、雇主账户号码及工资组别编号",
                "MPF 供款表按计划下载 XLSX，全部计划下载 ZIP；供款金额直接采用同月 Payroll 结果",
            ],
            "en": [
                "Employee files show the current MPF scheme, Member Account No. and effective date while retaining prior scheme records",
                "Reference Data maintains MPF scheme name, employer account number and payroll group ID",
                "Download one MPF XLSX per scheme or a ZIP for all schemes, using the same month's Payroll contribution results",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "任職、薪酬及 MPF 操作統一為「新增記錄」，後續變動合併於「變更歷史」查看",
                "MPF 資料缺失只阻止 MPF 供款表，不阻止已齊備考勤、薪酬及銀行資料的 Payroll",
            ],
            "zh-Hans": [
                "任职、薪酬及 MPF 操作统一为“新增记录”，后续变动合并在“变更历史”查看",
                "MPF 资料缺失只阻止 MPF 供款表，不阻止已齐备考勤、薪酬及银行资料的 Payroll",
            ],
            "en": [
                "Assignment, salary and MPF actions use Add record wording, with later activity consolidated under Change history",
                "Missing MPF metadata blocks only MPF reports, not otherwise payroll-ready employees",
            ],
        },
        "limitations": {
            "zh-Hant": ["MPF 計劃月中轉換本版不拆分同月供款；請由 HR 核對後處理。"],
            "zh-Hans": ["MPF 计划月中转换本版不拆分同月供款；请由 HR 核对后处理。"],
            "en": ["A mid-month MPF scheme change is not split within one contribution month and requires HR review."],
        },
    },
    {
        "version": "V0.2.2",
        "date": "2026-08-11",
        "title": {
            "zh-Hant": "員工狀態工作區與考勤免交流程",
            "zh-Hans": "员工状态工作区与考勤免交流程",
            "en": "Employee readiness workspace and attendance exemptions",
        },
        "features": {
            "zh-Hant": [
                "員工總表集中顯示員工檔案、所選月份考勤及出糧狀態，工作總覽只保留需處理摘要",
                "員工、年假與考勤管理採用左側條件、右側結果的統一工作區；考勤新增單月免交與長期免交子版塊",
                "新建及個人資料可設定每月是否需要考勤，預設需要；長期免交按全勤及零 OT／E-CALL 計算",
            ],
            "zh-Hans": [
                "员工总表集中显示员工档案、所选月份考勤及出粮状态，工作总览只保留需处理摘要",
                "员工、年假与考勤管理采用左侧条件、右侧结果的统一工作区；考勤新增单月免交与长期免交子板块",
                "新建及个人资料可设置每月是否需要考勤，默认需要；长期免交按全勤及零 OT／E-CALL 计算",
            ],
            "en": [
                "The employee register is the full Employee File, selected-month Attendance and Payroll Status matrix; the Dashboard keeps a compact action summary",
                "Employee, annual-leave and attendance workspaces use left-side context and filters with right-side results; attendance has separate monthly and long-term exemption views",
                "Employee creation and personal details can set whether monthly attendance is required; exemptions use full attendance with zero OT and E-CALL",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "出糧銀行資料與可選的銀行賬戶文件分開；後者不再阻止出糧",
                "雇傭合約、已填寫／未填寫、已存檔／未存檔、已收／未收／免交及可出糧／不可出糧用語已統一",
                "銀行名稱及帳號由 HR 儲存後直接供 Payroll 使用，不再要求重複核對新銀行資料",
                "員工總表欄位標題固定於名單頂端，向下查看員工時仍可辨認各狀態欄位",
                "員工總表將同月份的考勤及出糧結果合併為一個狀態欄",
            ],
            "zh-Hans": [
                "出粮银行资料与可选的银行账户文件分开；后者不再阻止出粮",
                "雇佣合同、已填写／未填写、已存档／未存档、已收／未收／免交及可出粮／不可出粮用语已统一",
                "银行名称及账号由 HR 保存后直接供 Payroll 使用，不再要求重复核对新银行资料",
                "员工总表字段标题固定在名单顶部，向下查看员工时仍可辨认各状态字段",
                "员工总表将同月份的考勤及出粮结果合并为一个状态字段",
            ],
            "en": [
                "Required payroll bank details are separated from the optional bank account document, which no longer blocks payroll",
                "Employment Contract and source-specific status wording are consistent across the UI",
                "Bank name and account details are ready for Payroll once HR saves them, without a second verification step",
                "Employee-register column headers remain visible while scrolling through the roster",
                "The employee register combines attendance and payroll results for the selected month in one status column",
            ],
        },
        "limitations": {
            "zh-Hant": [],
            "zh-Hans": [],
            "en": [],
        },
    },
    {
        "version": "V0.2.1",
        "date": "2026-08-11",
        "title": {
            "zh-Hant": "共用資料完整度與正式環境保護",
            "zh-Hans": "共用资料完整度与正式环境保护",
            "en": "Shared readiness and production safeguards",
        },
        "features": {
            "zh-Hant": [
                "工作總覽以每名員工一行顯示員工資料、當月考勤及 Payroll 阻塞項，齊備為綠色、缺失為紅色",
                "缺項直接連到員工檔案、考勤或 Payroll 處理位置，不再維護與真實資料分離的進度備註",
            ],
            "zh-Hans": [
                "工作总览以每名员工一行显示员工资料、当月考勤及 Payroll 阻塞项，齐备为绿色、缺失为红色",
                "缺项直接连到员工档案、考勤或 Payroll 处理位置，不再维护与真实资料分离的进度备注",
            ],
            "en": [
                "The Dashboard shows employee data, selected-month attendance and Payroll blockers in one compact row per employee",
                "Each missing item links to its source workflow instead of maintaining separate progress notes",
            ],
        },
        "improvements": {
            "zh-Hant": ["附件上傳、登入及錯誤頁加入一致而可理解的安全提示"],
            "zh-Hans": ["附件上传、登录及错误页面加入一致且易懂的安全提示"],
            "en": ["Uploads, login and error pages now use consistent safeguards and clear messages"],
        },
        "limitations": {
            "zh-Hant": [],
            "zh-Hans": [],
            "en": [],
        },
    },
    {
        "version": "V0.2.0",
        "date": "2026-08-10",
        "title": {
            "zh-Hant": "考勤詳情分類檢視",
            "zh-Hans": "考勤详情分类查看",
            "en": "Focused attendance status views",
        },
        "features": {
            "zh-Hant": [
                "考勤詳情以摘要卡切換未收、已收及本月無需考勤，右側每次只顯示一類名單",
                "工作總覽待辦按員工彙整為一行，點擊後才展開缺失項目、進度及備註",
            ],
            "zh-Hans": [
                "考勤详情以摘要卡切换未收、已收及本月无需考勤，右侧每次只显示一类名单",
                "工作总览待办按员工汇总为一行，点击后才展开缺失项目、进度及备注",
            ],
            "en": [
                "Attendance Details switches between Missing, Received and Not required summaries, showing one roster at a time",
                "Dashboard tasks are grouped into one collapsed row per employee, with missing items, progress and notes shown on demand",
            ],
        },
        "improvements": {
            "zh-Hant": ["預設打開未收名單；設定或恢復本月考勤要求後，自動返回相應分類"],
            "zh-Hans": ["默认打开未收名单；设置或恢复本月考勤要求后，自动返回相应分类"],
            "en": ["Missing opens by default, and attendance requirement changes return to the relevant category"],
        },
        "limitations": {
            "zh-Hant": ["應收只顯示總數；人員會按實際狀態出現在未收、已收或本月無需考勤名單。"],
            "zh-Hans": ["应收只显示总数；人员会按实际状态出现在未收、已收或本月无需考勤名单。"],
            "en": ["Expected is a total only; employees appear under Missing, Received or Not required according to their status."],
        },
    },
    {
        "version": "V0.1.9",
        "date": "2026-08-10",
        "title": {
            "zh-Hant": "可出糧員工預覽與彈性導出",
            "zh-Hans": "可出粮员工预览与灵活导出",
            "en": "Ready-employee payroll review and flexible export",
        },
        "features": {
            "zh-Hant": [
                "Payroll 員工清單可勾選單人或多人直接導出，跨組別時自動下載 ZIP",
                "左側可一鍵導出目前全部可出糧員工，待補資料員工不會阻塞或混入",
            ],
            "zh-Hans": [
                "Payroll 员工清单可勾选单人或多人直接导出，跨组别时自动下载 ZIP",
                "左侧可一键导出目前全部可出粮员工，待补资料员工不会阻塞或混入",
            ],
            "en": [
                "Export one or more selected employees directly from the Payroll list, with automatic ZIP output across groups",
                "The side rail exports all currently ready employees without blockers stopping or entering the output",
            ],
        },
        "improvements": {
            "zh-Hant": ["項目 Payroll 摘要移到員工明細上方；清單本身即為本月預覽，不再開啟額外預覽面板"],
            "zh-Hans": ["项目 Payroll 摘要移到员工明细上方；清单本身即为本月预览，不再打开额外预览面板"],
            "en": ["Project payroll totals now sit above employee details, and the list itself is the monthly preview"],
        },
        "limitations": {
            "zh-Hant": ["單人導出仍使用所屬 Payroll 組別的正式工作表範本，不是獨立薪金單格式。"],
            "zh-Hans": ["单人导出仍使用所属 Payroll 组别的正式工作表模板，不是独立工资单格式。"],
            "en": ["Single-employee export uses the employee's group payroll workbook template rather than a separate payslip format."],
        },
    },
    {
        "version": "V0.1.8",
        "date": "2026-08-10",
        "title": {
            "zh-Hant": "考勤管理三區導航與批次卡片總覽",
            "zh-Hans": "考勤管理三区导航与批次卡片总览",
            "en": "Attendance navigation and batch card overview",
        },
        "features": {
            "zh-Hant": [
                "考勤管理左側分為考勤詳情、長期免交考勤及考勤收集三個子版塊",
                "考勤收集右側以卡片顯示所選批次的全部 PDF 及處理狀態",
            ],
            "zh-Hans": [
                "考勤管理左侧分为考勤详情、长期免交考勤及考勤收集三个子版块",
                "考勤收集右侧以卡片显示所选批次的全部 PDF 及处理状态",
            ],
            "en": [
                "Attendance Management now has separate Details, Long-term Exemptions and Collection sections",
                "Attendance Collection shows every PDF in the selected batch as a status card",
            ],
        },
        "improvements": {
            "zh-Hant": ["上傳及最近批次只在考勤收集顯示；退出詳情會返回同一批次卡片總覽"],
            "zh-Hans": ["上传及最近批次只在考勤收集显示；退出详情会返回同一批次卡片总览"],
            "en": ["Upload and recent batches appear only in Collection, and exiting detail returns to the same batch overview"],
        },
        "limitations": {
            "zh-Hant": ["批次卡片顯示文件名稱及狀態，不產生 PDF 頁面縮圖。"],
            "zh-Hans": ["批次卡片显示文件名称及状态，不生成 PDF 页面缩略图。"],
            "en": ["Batch cards show filenames and status without generating PDF page thumbnails."],
        },
    },
    {
        "version": "V0.1.7",
        "date": "2026-08-10",
        "title": {
            "zh-Hant": "長期免交考勤與單人薪酬預覽",
            "zh-Hans": "长期免交考勤与单人薪酬预览",
            "en": "Long-term attendance exemptions and employee payroll preview",
        },
        "features": {
            "zh-Hant": [
                "考勤管理集中提供長期免交及批量恢復，按生效月份保存並記錄操作",
                "薪酬摘要人數可點擊查看員工清單，並提供單人薪酬明細預覽",
                "考勤批次卡片進入專注詳情後隱藏左欄，PDF 預設關閉縮圖導航",
            ],
            "zh-Hans": [
                "考勤管理集中提供长期免交及批量恢复，按生效月份保存并记录操作",
                "薪酬摘要人数可点击查看员工清单，并提供单人薪酬明细预览",
                "考勤批次卡片进入专注详情后隐藏左栏，PDF 默认关闭缩略图导航",
            ],
            "en": [
                "Attendance Management now provides effective-dated long-term exemptions and batch restoration with audit records",
                "Payroll headcounts open employee lists with individual payroll breakdown previews",
                "Attendance batch cards open a focused detail view with the side rail and PDF thumbnails hidden",
            ],
        },
        "improvements": {
            "zh-Hant": ["待補資料員工不顯示推測金額；月度考勤設定仍優先於長期政策"],
            "zh-Hans": ["待补资料员工不显示推测金额；月度考勤设置仍优先于长期政策"],
            "en": ["Employees with hard blockers show no estimated pay, and month-specific attendance settings still override long-term policy"],
        },
        "limitations": {
            "zh-Hant": ["長期免交仍須由 HR 核對預設全勤、項目及法定假日是否符合實際。"],
            "zh-Hans": ["长期免交仍须由 HR 核对默认全勤、项目及法定假日是否符合实际。"],
            "en": ["HR must still verify default attendance, project allocation and statutory holidays for long-term exemptions."],
        },
    },
    {
        "version": "V0.1.6",
        "date": "2026-08-10",
        "title": {
            "zh-Hant": "員工搜尋與離職後考勤名單修正",
            "zh-Hans": "员工搜索与离职后考勤名单修正",
            "en": "Employee search and post-departure attendance fixes",
        },
        "features": {
            "zh-Hant": [
                "員工總表支援繁體、簡體中文姓名互相搜尋",
                "考勤未收名單按所選月份及實際任職期間判斷",
            ],
            "zh-Hans": [
                "员工总表支持繁体、简体中文姓名互相搜索",
                "考勤未收名单按所选月份及实际任职期间判断",
            ],
            "en": [
                "Employee search now matches names across Traditional and Simplified Chinese",
                "Missing attendance now follows the selected month and actual employment periods",
            ],
        },
        "improvements": {
            "zh-Hant": ["離職當月仍保留應收考勤；離職後月份不再顯示為未收"],
            "zh-Hans": ["离职当月仍保留应收考勤；离职后月份不再显示为未收"],
            "en": ["Attendance remains due for the departure month but not for later months"],
        },
        "limitations": {
            "zh-Hant": ["英文姓名及員工編號仍按原輸入內容搜尋。"],
            "zh-Hans": ["英文姓名及员工编号仍按原输入内容搜索。"],
            "en": ["English names and employee numbers continue to use their original text."],
        },
    },
    {
        "version": "V0.1.5",
        "date": "2026-08-07",
        "title": {
            "zh-Hant": "可逆的免交考勤表設定",
            "zh-Hans": "可逆的免交考勤表设置",
            "en": "Reversible attendance exemption",
        },
        "features": {
            "zh-Hant": [
                "考勤預設仍為必須；HR 可按員工及月份標記本月無需考勤表",
                "免交考勤表時按預設全勤計算，OT、大 E-CALL及普通 E-CALL均為 0",
                "可隨時改回需要考勤，再按正常流程導入考勤 PDF",
            ],
            "zh-Hans": [
                "考勤默认仍为必须；HR 可按员工及月份标记本月无需考勤表",
                "免交考勤表时按默认全勤计算，OT、大 E-CALL 及普通 E-CALL 均为 0",
                "可随时改回需要考勤，再按正常流程导入考勤 PDF",
            ],
            "en": [
                "Attendance remains required by default; HR can exempt an employee for a selected month",
                "An exemption uses default full attendance with OT, Large E-CALL and ordinary E-CALL set to zero",
                "HR can require attendance again and then import the attendance PDF normally",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "標記免交及改回需要考勤均保存操作記錄",
                "Payroll 頁常駐顯示免交考勤表計算規則，受影響員工另有核對提示",
                "免交及恢復考勤使用站內確認視窗，清楚顯示員工及考勤年月",
            ],
            "zh-Hans": [
                "标记免交及改回需要考勤均保存操作记录",
                "Payroll 页面常驻显示免交考勤表计算规则，受影响员工另有核对提示",
                "免交及恢复考勤使用站内确认窗口，清楚显示员工及考勤年月",
            ],
            "en": [
                "Both exemption and restoration are recorded in the audit trail",
                "Payroll keeps the exemption rule visible and adds a warning to affected employees",
                "In-app confirmations show the employee and attendance month before either change",
            ],
        },
        "limitations": {
            "zh-Hant": ["HR 仍須在導出前核對預設全勤日數、項目及法定假日。"],
            "zh-Hans": ["HR 仍须在导出前核对默认全勤天数、项目及法定假日。"],
            "en": ["HR must still verify default attendance days, project allocation and statutory holidays before export."],
        },
    },
    {
        "version": "V0.1.4",
        "date": "2026-08-07",
        "title": {
            "zh-Hant": "年假來源與離職結算",
            "zh-Hans": "年假来源与离职结算",
            "en": "Annual-leave sources and Final Payment",
        },
        "features": {
            "zh-Hant": [
                "年假分開管理 2023 年及以前永久結餘與 2024 年起年度結餘，並支援公司批准的特別順延日期",
                "新增離職結算工作區，集中核對離職月實際考勤、未休假期、代通知金及遣散／長期服務金",
                "Final Payment 可按三個 Payroll 組別輸出；選擇全部會下載包含三份 XLSX 的 ZIP",
            ],
            "zh-Hans": [
                "年假分开管理 2023 年及以前永久结余与 2024 年起年度结余，并支持公司批准的特别顺延日期",
                "新增离职结算工作区，集中核对离职月实际考勤、未休假期、代通知金及遣散／长期服务金",
                "Final Payment 可按三个 Payroll 组别输出；选择全部会下载包含三份 XLSX 的 ZIP",
            ],
            "en": [
                "Annual leave now separates the permanent 2023-and-earlier balance from annual balances from 2024 onward, including approved extension dates",
                "A Final Payment workspace reviews actual final-month attendance, unused leave, payment in lieu and severance/long-service payment",
                "Final Payment exports by the three Payroll groups; All downloads a ZIP containing three XLSX files",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "登記年假可分別指定使用舊年假及 2024 起年假；後者自動先扣最早到期且仍有效的年度",
                "離職結算頁常駐顯示假期補薪、2025-05-01 轉制、款額上限及 MPF 抵銷規則",
                "Final Payment 使用清理後的正式範本，保留基本工資、OT、假日、總額及實發金額 Excel 公式",
                "Final Payment 頁面清楚標示勞工處官方來源，匯出檔新增「計算說明」工作表保存相同規則摘要",
            ],
            "zh-Hans": [
                "登记年假可分别指定使用旧年假及 2024 起年假；后者自动先扣最早到期且仍有效的年度",
                "离职结算页常驻显示假期补薪、2025-05-01 转制、款额上限及 MPF 抵销规则",
                "Final Payment 使用清理后的正式模板，保留基本工资、OT、假日、总额及实发金额 Excel 公式",
                "Final Payment 页面清楚标示劳工处官方来源，导出文件新增“计算说明”工作表保存相同规则摘要",
            ],
            "en": [
                "A leave entry can split usage between legacy and post-2024 leave; post-2024 leave uses the oldest valid balance first",
                "Final Payment keeps leave-pay, 2025-05-01 transition, payment-cap and MPF-offset rules visible on the page",
                "The cleaned Final Payment template retains Excel formulas for basic pay, OT, holidays, totals and actual payment",
                "Final Payment identifies the Labour Department sources and adds a Calculation Notes sheet to every exported workbook",
            ],
        },
        "limitations": {
            "zh-Hant": ["遣散費、長期服務金、平均工資、未休法定假日及資格仍須由 HR 按實際情況核對。"],
            "zh-Hans": ["遣散费、长期服务金、平均工资、未休法定假日及资格仍须由 HR 按实际情况核对。"],
            "en": ["HR must still verify eligibility, average wages, unused statutory holidays and final severance/long-service amounts."],
        },
    },
    {
        "version": "V0.1.3",
        "date": "2026-08-06",
        "title": {
            "zh-Hant": "一致的資料修正視窗",
            "zh-Hans": "一致的资料修正窗口",
            "en": "Consistent record correction dialogs",
        },
        "features": {
            "zh-Hant": [
                "任職、薪酬、證件、VISA、學歷技能、附件、Payroll 調整及年假統一在獨立修正視窗處理",
                "修正視窗的內容可獨立滾動，保存及取消按鈕固定顯示",
            ],
            "zh-Hans": [
                "任职、薪酬、证件、VISA、学历技能、附件、Payroll 调整及年假统一在独立修正窗口处理",
                "修正窗口的内容可独立滚动，保存及取消按钮固定显示",
            ],
            "en": [
                "Employment, salary, credentials, VISA, qualifications, attachments, Payroll adjustments and leave use a shared correction dialog",
                "Dialog content scrolls independently while Save and Cancel remain visible",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "修正表單不再被表格或卡片裁切，也不會跑到畫面之外",
                "桌面使用置中視窗，窄屏使用全屏表單；右鍵快速修正仍開啟相同視窗",
                "職務／工種保留多選能力，但改為可收合選單；選擇後會自動收起並顯示已選職務",
                "快速新增已移入相應下拉選單或輸入框底部，不再於每個欄位標題旁重複顯示加號",
                "新增名稱與現有選項重複時會指出已有選項，不再顯示 JSON 或伺服器錯誤術語",
            ],
            "zh-Hans": [
                "修正表单不再被表格或卡片裁切，也不会跑到画面之外",
                "桌面使用居中窗口，窄屏使用全屏表单；右键快速修正仍打开相同窗口",
                "职务／工种保留多选能力，但改为可收合选单；选择后会自动收起并显示已选职务",
                "快速新增已移入相应下拉选单或输入框底部，不再于每个字段标题旁重复显示加号",
                "新增名称与现有选项重复时会指出已有选项，不再显示 JSON 或服务器错误术语",
            ],
            "en": [
                "Correction forms are no longer clipped by tables or cards or positioned outside the viewport",
                "Desktop uses a centred dialog, narrow screens use a full-screen form, and right-click opens the same correction dialog",
                "Position and trade remains multi-select, but now collapses after each choice and displays the selected roles",
                "Quick add now appears inside the relevant select or beneath its input instead of repeating plus buttons beside every label",
                "Duplicate quick-add names now identify the existing option instead of exposing JSON or server error terminology",
            ],
        },
        "limitations": {
            "zh-Hant": ["本版只統一資料修正與新增記錄視窗，不改變原有資料及審計規則。"],
            "zh-Hans": ["本版只统一资料修正与新增记录窗口，不改变原有数据及审计规则。"],
            "en": ["This release changes the editing interface only; existing data and audit rules are unchanged."],
        },
    },
    {
        "version": "V0.1.2",
        "date": "2026-08-06",
        "title": {
            "zh-Hant": "當前任職與調整流程",
            "zh-Hans": "当前任职与调整流程",
            "en": "Current assignment and adjustment workflow",
        },
        "features": {
            "zh-Hant": [
                "當前任職卡片改以主要職務作標題，並直接顯示項目、部門、聘用及發薪等完整任職資料",
                "未有任職時顯示「建立初始任職」；已有任職時顯示「調整任職」並自動帶入目前資料",
                "未來生效的任職調整會清楚提示生效日期，保存後不會提前取代目前任職",
            ],
            "zh-Hans": [
                "当前任职卡片改以主要职务作标题，并直接显示项目、部门、聘用及发薪等完整任职资料",
                "没有任职时显示“建立初始任职”；已有任职时显示“调整任职”并自动带入当前资料",
                "未来生效的任职调整会清楚提示生效日期，保存后不会提前取代当前任职",
            ],
            "en": [
                "The current-assignment card uses the primary position as its heading and shows the complete assignment details",
                "Profiles without an assignment show Create initial assignment; later adjustments are prefilled from the current record",
                "Future-dated assignment changes state their effective date and do not replace today's assignment early",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "沒有指定項目時明確顯示「項目：未分配」，不再把整筆任職誤顯示為未填寫",
                "任職歷史的修正表單可修改聘用、發薪、社保及勞務派遣單位",
                "保存提示會分辨初始任職、立即生效調整及未來生效調整",
            ],
            "zh-Hans": [
                "没有指定项目时明确显示“项目：未分配”，不再把整笔任职误显示为未填写",
                "任职历史的修正表单可修改聘用、发薪、社保及劳务派遣单位",
                "保存提示会区分初始任职、立即生效调整及未来生效调整",
            ],
            "en": [
                "An assignment without a project now says Project: Unassigned instead of implying the whole assignment is missing",
                "Historical assignment corrections can edit employer, payroll, social-insurance and labour-dispatch entities",
                "Save messages distinguish initial, immediately effective and future-dated assignments",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "項目仍可留空，以配合沒有固定工程項目的管理及總部人員；HR 應按實際任職填寫",
            ],
            "zh-Hans": [
                "项目仍可留空，以配合没有固定工程项目的管理及总部人员；HR 应按实际任职填写",
            ],
            "en": [
                "Project remains optional for management and head-office staff without a fixed site",
            ],
        },
    },
    {
        "version": "V0.1.1",
        "date": "2026-08-04",
        "title": {
            "zh-Hant": "員工錄入即時補充下拉選項",
            "zh-Hans": "员工录入即时补充下拉选项",
            "en": "Inline reference-data creation during employee entry",
        },
        "features": {
            "zh-Hant": [
                "員工檔案的銀行、學歷、項目、部門、職務、單位、幣種、證件及 VISA 等欄位可直接快速新增選項",
                "快速新增視窗先列出已有選項，新增成功後會立即套用到尚未提交的員工表單",
                "完整基礎資料清單以新分頁開啟，原員工表單及目前頁籤保持不變",
            ],
            "zh-Hans": [
                "员工档案的银行、学历、项目、部门、职务、单位、币种、证件及 VISA 等字段可直接快速新增选项",
                "快速新增窗口先列出已有选项，新增成功后会立即套用到尚未提交的员工表单",
                "完整基础资料清单以新分页打开，原员工表单及当前页签保持不变",
            ],
            "en": [
                "Bank, education, project, department, position, entity, currency, credential and VISA options can be created from the employee profile",
                "The quick-add dialog shows existing values first and applies a new value to the unsaved employee form immediately",
                "The full reference-data list opens in a new tab while the employee form and active profile tab remain in place",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "從員工檔案開啟完整基礎資料時保留返回路徑；保存選項後仍可直接返回原員工",
                "項目快速新增同時保留工作地區及日工 OT 除數設定",
                "快速新增與返回流程補齊繁體中文、簡體中文及英文介面文案",
            ],
            "zh-Hans": [
                "从员工档案打开完整基础资料时保留返回路径；保存选项后仍可直接返回原员工",
                "项目快速新增同时保留工作地区及日工 OT 除数设置",
                "快速新增与返回流程补齐繁体中文、简体中文及英文界面文案",
            ],
            "en": [
                "Opening the full list from an employee profile preserves a direct return path after saving",
                "Quick project creation retains work-region and daily OT divisor settings",
                "The quick-add and return flow is translated in Traditional Chinese, Simplified Chinese and English",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "員工類別仍須在完整基礎資料頁維護，避免快速新增時誤設員工編號前綴",
            ],
            "zh-Hans": [
                "员工类别仍须在完整基础资料页维护，避免快速新增时误设员工编号前缀",
            ],
            "en": [
                "Employee categories remain full-list only to protect employee-number prefix rules",
            ],
        },
    },
    {
        "version": "V0.1.0",
        "date": "2026-07-31",
        "title": {
            "zh-Hant": "HR 核心工作區與修正流程",
            "zh-Hans": "HR 核心工作区与修正流程",
            "en": "HR core workspace and correction workflows",
        },
        "features": {
            "zh-Hant": [
                "Payroll 頁開啟後即時計算，切換月份或組別會自動重算，導出時自動保存計算快照",
                "身份證件、員工證件、VISA、學歷技能、任職、薪酬、考勤、年假及 Payroll 調整均提供修正或撤回入口",
                "年假管理成為獨立一級功能，可修正本年應享年假並以 0.5 日登記或撤回年假",
                "Dashboard 待辦支援類型、進度及員工篩選，進度備註保留操作者和時間",
                "一級導航重整為工作總覽、員工管理、年假管理、考勤管理、薪酬與匯出及基礎資料",
                "Payroll 移入「薪酬與匯出」，同一工作區提供薪酬計算、員工資料及附件打包",
                "Dashboard 本月預計出糧改用實際 Payroll 引擎計算，並顯示尚缺必要資料的人數",
                "確認 HR 可新增、修改、停用及刪除未使用的基礎資料與項目",
                "一次性員工初始化精簡為員工編號及中文／英文姓名，不再從初始化 XLSX 建立其他人事資料",
            ],
            "zh-Hans": [
                "Payroll 页面打开后即时计算，切换月份或组别会自动重算，导出时自动保存计算快照",
                "身份证件、员工证件、VISA、学历技能、任职、薪酬、考勤、年假及 Payroll 调整均提供修正或撤回入口",
                "年假管理成为独立一级功能，可修正本年应享年假并以 0.5 日登记或撤回年假",
                "Dashboard 待办支持类型、进度及员工筛选，进度备注保留操作者和时间",
                "一级导航重整为工作总览、员工管理、年假管理、考勤管理、薪酬与导出及基础资料",
                "Payroll 移入“薪酬与导出”，同一工作区提供薪酬计算、员工资料及附件打包",
                "Dashboard 本月预计出粮改用实际 Payroll 引擎计算，并显示尚缺必要资料的人数",
                "确认 HR 可新增、修改、停用及删除未使用的基础资料与项目",
                "一次性员工初始化精简为员工编号及中文／英文姓名，不再从初始化 XLSX 建立其他人事资料",
            ],
            "en": [
                "Payroll calculates on page load, recalculates when month or group changes, and saves a snapshot during export",
                "Identity, credentials, VISA, qualifications, employment, salary, attendance, leave and Payroll adjustments can be corrected or withdrawn",
                "Annual Leave is a primary module with editable entitlement and half-day record correction or withdrawal",
                "Dashboard tasks can be filtered and retain progress-note author and time",
                "Primary navigation now follows HR tasks: overview, employees, leave, attendance, payroll and exports, and reference data",
                "Payroll calculation, employee exports and attachment bundles share one Payroll & Exports workspace",
                "Dashboard payroll estimates use the live payroll engine and show employees missing required data",
                "HR can create, edit, disable and delete unused reference values and projects",
                "One-time employee initialization now accepts only employee number and Chinese or English name",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "錯誤附件以替換處理，舊檔標記為已替換；缺少附件可直接補件，不覆蓋歷史",
                "員工刪除會同步清理考勤批次及 Payroll 快照的孤立資料",
                "員工檔案直接顯示每月四段考勤、考勤 PDF、最近 Payroll 快照及調整項目",
                "考勤及年假在沒有資料時改用清楚的單一開始提示，不再顯示大片空白工作區",
                "Payroll 首屏先顯示公式、可出糧人數及金額摘要，詳細規則仍可在同頁展開查看",
                "基礎資料按用途分組；有既有資料引用的選項只能停用，不能刪除並清空歷史",
                "身份證件號碼會忽略空格及標點比對，避免同一有效證件被分配給兩名員工",
                "新增 HR 權限自動測試，持續防止基礎資料維護權限意外退化",
                "版本序列更正為 V0.0.9 之後直接進入 V0.1.0",
            ],
            "zh-Hans": [
                "错误附件以替换处理，旧文件标记为已替换；缺少附件可直接补件，不覆盖历史",
                "员工删除会同步清理考勤批次及 Payroll 快照的孤立资料",
                "员工档案直接显示每月四段考勤、考勤 PDF、最近 Payroll 快照及调整项目",
                "考勤及年假在没有资料时改用清楚的单一开始提示，不再显示大片空白工作区",
                "Payroll 首屏先显示公式、可出粮人数及金额摘要，详细规则仍可在同页展开查看",
                "基础资料按用途分组；有既有资料引用的选项只能停用，不能删除并清空历史",
                "身份证件号码会忽略空格及标点比对，避免同一有效证件被分配给两名员工",
                "新增 HR 权限自动测试，持续防止基础资料维护权限意外退化",
                "版本序列更正为 V0.0.9 之后直接进入 V0.1.0",
            ],
            "en": [
                "Wrong attachments are replaced while the old file remains historical; missing evidence can be supplemented",
                "Deleting a test employee also removes orphan attendance-batch and Payroll snapshot shells",
                "Employee profiles show monthly four-part attendance, PDF, latest Payroll snapshot and adjustments",
                "Attendance and leave use a single clear start state when no records exist",
                "Payroll shows formula, readiness and monetary summaries first while retaining expandable detailed rules",
                "Reference data is grouped by use; referenced options can be disabled but not deleted",
                "Identity comparison ignores spacing and punctuation to prevent duplicate active identities across employees",
                "Automated HR permission coverage prevents reference-data maintenance regressions",
                "The release sequence now moves directly from V0.0.9 to V0.1.0",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "右鍵只作快速開啟修正表單；所有必要操作仍保留可見按鈕",
                "Payroll 及法定金額仍須由 HR 依合同、考勤和法例核對",
                "有既有資料引用的基礎資料不能刪除；HR 及 Admin 均應改為停用",
            ],
            "zh-Hans": [
                "右键只用于快速打开修正表单；所有必要操作仍保留可见按钮",
                "Payroll 及法定金额仍须由 HR 按合同、考勤和法例核对",
                "有既有资料引用的基础资料不能删除；HR 及 Admin 均应改为停用",
            ],
            "en": [
                "Right-click is only a shortcut to correction forms; every required action remains visibly available",
                "HR must still verify Payroll and statutory amounts against contracts, attendance and applicable rules",
                "Referenced values cannot be deleted by either role and must be disabled instead",
            ],
        },
    },
    {
        "version": "V0.0.9",
        "date": "2026-07-30",
        "title": {
            "zh-Hant": "員工檔案、四段考勤與人事修正流程",
            "zh-Hans": "员工档案、四段考勤与人事修正流程",
            "en": "Employee records, four-part attendance and corrections",
        },
        "features": {
            "zh-Hant": [
                "員工檔案改為先顯示當前個人、任職、薪酬、證件及附件狀態，相關歷史時間線放在同一頁籤",
                "考勤及 Payroll 使用本月實際、本月預估、上月實際及上月原預估四段多退少補",
                "建造業日工 MPF 按官方每日相關入息級距計算，65 歲或以上自動不供款",
                "年假支援起止日期及上午／下午，以 0.5 日為最小單位",
                "報表中心新增僱員薪金證明書，從最近三個已生成 Payroll 月份套用 Excel 範本",
            ],
            "zh-Hans": [
                "员工档案改为先显示当前个人、任职、薪酬、证件及附件状态，相关历史时间线放在同一页签",
                "考勤及 Payroll 使用本月实际、本月预计、上月实际及上月原预计四段多退少补",
                "建筑业日工 MPF 按官方每日相关入息级距计算，65 岁或以上自动不供款",
                "年假支持起止日期及上午／下午，以 0.5 日为最小单位",
                "报表中心新增雇员薪金证明书，从最近三个已生成 Payroll 月份套用 Excel 模板",
            ],
            "en": [
                "Employee tabs now show current personal, employment, salary, credential and document state before the related history",
                "Attendance and Payroll reconcile current actual, current forecast, previous actual and previous forecast periods",
                "Construction casual-worker MPF uses the official daily relevant-income scale; employees aged 65 or above are exempt",
                "Annual leave supports start/end dates and morning/afternoon sessions in half-day units",
                "Report Center can generate an Employee Salary Certificate from the latest three generated Payroll months",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "未到最後工作日前，員工仍保持在職並出現在考勤及 Payroll；離職資料可更正或撤回",
                "任職及薪酬記錄可補交憑證、更正或撤回，舊記錄與操作軌跡繼續保留",
                "附件可直接預覽、下載、替換或作廢；替換後所有相關證件、考勤及人事記錄同步改用新文件",
                "代通知金、遣散費及長期服務金使用已生成 Payroll 平均工資作可修正的參考估算",
            ],
            "zh-Hans": [
                "未到最后工作日前，员工仍保持在职并出现在考勤及 Payroll；离职资料可更正或撤回",
                "任职及薪酬记录可补交凭证、更正或撤回，旧记录与操作轨迹继续保留",
                "附件可直接预览、下载、替换或作废；替换后所有相关证件、考勤及人事记录同步改用新文件",
                "代通知金、遣散费及长期服务金使用已生成 Payroll 平均工资作可修正的参考估算",
            ],
            "en": [
                "A future last working day keeps the employee active in attendance and Payroll; termination details can be corrected or withdrawn",
                "Employment and salary records support evidence supplements, corrections and withdrawals while preserving history",
                "Documents can be previewed, downloaded, replaced or voided, and linked HR records follow the active replacement",
                "Payment in lieu, severance and long-service amounts use editable estimates based on generated Payroll history",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "離職法定權益只作初步估算；HR 必須按合同、實際情況及勞工處計算機再次核對",
                "考勤仍由 HR 預覽簽署 PDF 後人工錄入，不使用 OCR",
            ],
            "zh-Hans": [
                "离职法定权益只作初步估算；HR 必须按合同、实际情况及劳工处计算器再次核对",
                "考勤仍由 HR 预览签署 PDF 后人工录入，不使用 OCR",
            ],
            "en": [
                "Termination entitlements remain initial estimates and must be checked against the contract, facts and Labour Department calculator",
                "Attendance remains manual entry while previewing the signed PDF; OCR is not used",
            ],
        },
    },
    {
        "version": "V0.0.8",
        "date": "2026-07-30",
        "title": {
            "zh-Hant": "報表中心與操作提示重整",
            "zh-Hans": "报表中心与操作提示重整",
            "en": "Report Center and operator guidance refresh",
        },
        "features": {
            "zh-Hant": [
                "報表中心精簡為附件打包、員工資料總表及每月 Payroll 三個任務",
                "附件可按三寶、Staff Record、員工證件及資歷、合同、銀行證明及 CV、考勤月份或其他憑證打包",
                "員工資料總表 XLSX 同時提供證件及資歷、任職及薪酬歷史、附件索引工作表",
                "每月 Payroll 直接使用該月最新已保存結果及正式範本導出",
            ],
            "zh-Hans": [
                "报表中心精简为附件打包、员工资料总表及每月 Payroll 三个任务",
                "附件可按三宝、Staff Record、员工证件及资历、合同、银行证明及 CV、考勤月份或其他凭证打包",
                "员工资料总表 XLSX 同时提供证件及资历、任职及薪酬历史、附件索引工作表",
                "每月 Payroll 直接使用该月最新已保存结果及正式模板导出",
            ],
            "en": [
                "The Report Center now has three tasks: Attachment Bundle, Employee Records, and Monthly Payroll",
                "Attachments can be bundled by Three Treasures, Staff Record, credentials and qualifications, contracts, bank proof and CV, attendance month, or other evidence",
                "The employee records XLSX includes credentials, employment and salary history, and an attachment index",
                "Monthly Payroll uses the latest saved calculation for the month and the official templates",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "報表、基礎資料及附件說明改用 HR 當下需要採取的操作提示",
                "基礎資料提示新增避免重複、改名影響及 HA 日工 OT 除數說明",
                "附件、員工文件狀態及 Payroll 按鈕改用較直接的人事工作用語",
            ],
            "zh-Hans": [
                "报表、基础资料及附件说明改用 HR 当下需要采取的操作提示",
                "基础资料提示新增避免重复、改名影响及 HA 日工 OT 除数说明",
                "附件、员工文件状态及 Payroll 按钮改用较直接的人事工作用语",
            ],
            "en": [
                "Report, reference-data and attachment guidance now focuses on the next HR action",
                "Reference-data guidance now explains duplicate prevention, rename impact and the HA daily-worker OT divisor",
                "Document, attachment-status and Payroll actions now use clearer HR language",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "員工資料總表聚焦人事主資料及歷史；每月考勤及 Payroll 仍由各自匯出處理",
                "附件 ZIP 只包括目前有效文件，不包括已替換或已作廢文件",
            ],
            "zh-Hans": [
                "员工资料总表聚焦人事主资料及历史；每月考勤及 Payroll 仍由各自导出处理",
                "附件 ZIP 只包括目前有效文件，不包括已替换或已作废文件",
            ],
            "en": [
                "The employee records workbook covers complete employee records and history; monthly attendance and Payroll remain separate exports",
                "Attachment ZIP files include active documents only, not replaced or voided files",
            ],
        },
    },
    {
        "version": "V0.0.7",
        "date": "2026-07-29",
        "title": {
            "zh-Hant": "一級導航與考勤批次工作台",
            "zh-Hans": "一级导航与考勤批次工作台",
            "en": "Primary navigation and attendance batch workspace",
        },
        "features": {
            "zh-Hant": [
                "頂部改為 Dashboard、員工、考勤出糧、報表及設定五個一級區域",
                "左側只顯示當前區域的子功能及操作，不再同時堆疊全站選單與頁內左欄",
                "考勤左欄支援拖放或多選 PDF、目前批次進度、本批文件及最近批次",
            ],
            "zh-Hans": [
                "顶部改为 Dashboard、员工、考勤出粮、报表及设置五个一级区域",
                "左侧只显示当前区域的子功能及操作，不再同时堆叠全站菜单与页内左栏",
                "考勤左栏支持拖放或多选 PDF、当前批次进度、本批文件及最近批次",
            ],
            "en": [
                "Five primary areas now sit across the top: Dashboard, Employees, Attendance and Payroll, Reports, and Settings",
                "The left rail now shows only the current area's tools instead of duplicating global and page-level navigation",
                "The attendance rail supports PDF drag-and-drop or multi-select, current progress, batch files and recent batches",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "Dashboard 及員工頁移除無意義左欄，列表、卡片及表單可使用整個工作區",
                "考勤 PDF 預覽與右側錄入改為兩區，右側獨立捲動時預覽仍保持可見",
                "選中考勤批次後仍可看到最近批次，並可直接切換或刪除",
                "Payroll、報表中心及基礎資料共用情境左欄，不再各自佔用第二欄寬度",
            ],
            "zh-Hans": [
                "Dashboard 及员工页移除无意义左栏，列表、卡片及表单可使用整个工作区",
                "考勤 PDF 预览与右侧录入改为两区，右侧独立滚动时预览仍保持可见",
                "选中考勤批次后仍可看到最近批次，并可直接切换或删除",
                "Payroll、报表中心及基础资料共用情境左栏，不再各自占用第二栏宽度",
            ],
            "en": [
                "Dashboard and employee pages use the full workspace without an unnecessary rail",
                "Attendance uses a large PDF preview plus an independently scrolling entry panel",
                "Recent batches remain available while a current batch is selected",
                "Payroll, reports and reference data now share the contextual rail instead of creating a second sidebar",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "考勤仍由 HR 預覽 PDF 後人工錄入，不使用 OCR",
                "只借鑑 TMC 的導航及批次交互模式；HKR HR 程式、資料及服務仍完全獨立",
            ],
            "zh-Hans": [
                "考勤仍由 HR 预览 PDF 后人工录入，不使用 OCR",
                "只借鉴 TMC 的导航及批次交互模式；HKR HR 程序、资料及服务仍完全独立",
            ],
            "en": [
                "Attendance remains a manual entry workflow based on PDF preview; OCR is not used",
                "Only TMC navigation and batch interaction patterns are adapted; HKR HR code, data and services remain independent",
            ],
        },
    },
    {
        "version": "V0.0.6",
        "date": "2026-07-27",
        "title": {
            "zh-Hant": "固定左欄操作台與待辦精簡",
            "zh-Hans": "固定左栏操作台与待办精简",
            "en": "Fixed sidebar workspace and simpler reminders",
        },
        "features": {
            "zh-Hant": [
                "全站改用固定左側模組欄，右側工作區自動使用全部剩餘寬度",
                "銀行名稱、帳號及銀行證明任一未齊時，統一顯示一次「銀行資料未完成」",
            ],
            "zh-Hans": [
                "全站改用固定左侧模块栏，右侧工作区自动使用全部剩余宽度",
                "银行名称、账号及银行证明任一未齐时，统一显示一次“银行资料未完成”",
            ],
            "en": [
                "The application now uses a fixed left module rail with a workspace that fills all remaining width",
                "Missing bank name, account number or proof now produces one Bank details incomplete reminder",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "窄屏會把左欄轉為頁面上方的響應式模組區，避免內容互相擠壓",
                "銀行帳戶欄位與證明附件仍分開保存，只精簡 HR 看到的待辦提示",
            ],
            "zh-Hans": [
                "窄屏会把左栏转为页面上方的响应式模块区，避免内容互相挤压",
                "银行账户字段与证明附件仍分开保存，只精简 HR 看到的待办提示",
            ],
            "en": [
                "On narrow screens the rail becomes a responsive module area above the page content",
                "Bank fields and proof attachments remain separate records; only the HR reminder is consolidated",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "本版只調整共用介面骨架及提示文字，不改動 Payroll 計算或資料庫結構",
                "只借鑑 TMC 的操作模式；HKR HR 仍使用完全獨立的程式、資料及服務",
            ],
            "zh-Hans": [
                "本版只调整共用界面骨架及提示文字，不改动 Payroll 计算或数据库结构",
                "只借鉴 TMC 的操作模式；HKR HR 仍使用完全独立的程序、资料及服务",
            ],
            "en": [
                "This release changes the shared interface shell and reminders only; Payroll calculations and the database schema are unchanged",
                "Only the TMC interaction pattern is adapted; HKR HR remains fully independent in code, data and services",
            ],
        },
    },
    {
        "version": "V0.0.5",
        "date": "2026-07-26",
        "title": {
            "zh-Hant": "Payroll 公式化導出",
            "zh-Hans": "Payroll 公式化导出",
            "en": "Formula-driven Payroll exports",
        },
        "features": {
            "zh-Hant": [
                "三個 Payroll XLSX 的人工、OT、假期、E-CALL、總額、MPF及實發金額保留 Excel 公式",
                "HA 日工 OT 公式使用除數 10，其他日工項目使用除數 9",
                "一名員工跨項目多行時，MPF 公式按員工編號彙總後只在首行扣除",
            ],
            "zh-Hans": [
                "三个 Payroll XLSX 的人工、OT、假期、E-CALL、总额、MPF及实发金额保留 Excel 公式",
                "HA 日工 OT 公式使用除数 10，其他日工项目使用除数 9",
                "一名员工跨项目多行时，MPF 公式按员工编号汇总后只在首行扣除",
            ],
            "en": [
                "All three Payroll workbooks retain formulas for pay, OT, holidays, E-CALL, totals, MPF and net pay",
                "Daily-worker OT formulas use divisor 10 for HA projects and 9 otherwise",
                "For employees spanning project rows, MPF formulas aggregate by employee number and deduct on the first row only",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "Excel 開啟時會自動完整重算，HR 修改輸入數字後相關金額同步更新",
                "上月 21 日至月底欄位保留作核對，薪金總額只使用多付／少付差額，避免重複計薪",
                "公式結果已與網頁 Payroll 快照核對一致",
            ],
            "zh-Hans": [
                "Excel 打开时会自动完整重算，HR 修改输入数字后相关金额同步更新",
                "上月 21 日至月底字段保留作核对，薪金总额只使用多付／少付差额，避免重复计薪",
                "公式结果已与网页 Payroll 快照核对一致",
            ],
            "en": [
                "Excel performs a full recalculation on open so related amounts update when HR changes inputs",
                "Prior-tail columns remain visible for review while totals use only overpay or underpay reconciliation to prevent double payment",
                "Formula results were reconciled to the web Payroll snapshot",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "下載後修改 Excel 不會回寫網頁資料庫；正式資料變更仍須在員工或考勤頁保存",
                "HR 仍須在出糧前核對公式、考勤、MPF及最終實發金額",
            ],
            "zh-Hans": [
                "下载后修改 Excel 不会回写网页数据库；正式资料变更仍须在员工或考勤页保存",
                "HR 仍须在出粮前核对公式、考勤、MPF及最终实发金额",
            ],
            "en": [
                "Editing a downloaded workbook does not write back to the web database; official changes must be saved in employee or attendance records",
                "HR must still review formulas, attendance, MPF and final net pay before payment",
            ],
        },
    },
    {
        "version": "V0.0.4",
        "date": "2026-07-25",
        "title": {
            "zh-Hant": "HR 實操驗收修正",
            "zh-Hans": "HR 实操验收修正",
            "en": "HR hands-on acceptance fixes",
        },
        "features": {
            "zh-Hant": [
                "用戶管理改為精簡帳戶列表，按需開啟新增或管理對話框",
                "一次性員工初始化提供官方 XLSX 空白範本及逐行檢查",
                "員工資料保存後保留原頁籤，銀行核對提供明確成功提示",
                "報表中心分開缺失資料與 60 日內到期條件",
            ],
            "zh-Hans": [
                "用户管理改为精简帐户列表，按需打开新增或管理对话框",
                "一次性员工初始化提供官方 XLSX 空白模板及逐行检查",
                "员工资料保存后保留原页签，银行核对提供明确成功提示",
                "报表中心分开缺失资料与 60 日内到期条件",
            ],
            "en": [
                "User management now uses a compact account list with on-demand dialogs",
                "One-time employee initialization provides an official blank XLSX template and row validation",
                "Employee saves retain the active tab and bank verification gives clear feedback",
                "The report center separates missing-data and 60-day expiry filters",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "空白聯絡電話預設香港 +852，日工薪酬表單預設日薪及 HKD",
                "Payroll 三個範本的員工組別及日工薪酬標題已校正",
                "時間線及操作記錄改用可讀事件與資料類型名稱",
                "舊版匯入預覽及重複員工編號會被阻止確認",
            ],
            "zh-Hans": [
                "空白联系电话默认香港 +852，日工薪酬表单默认日薪及 HKD",
                "Payroll 三个模板的员工组别及日工薪酬标题已校正",
                "时间线及操作记录改用可读事件与资料类型名称",
                "旧版导入预览及重复员工编号会被阻止确认",
            ],
            "en": [
                "Blank phone fields default to Hong Kong +852; daily workers default to daily HKD salary entry",
                "Employee-group and daily-pay labels were corrected across the payroll templates",
                "Timeline and audit entries now use readable action and entity labels",
                "Legacy import previews and duplicate employee numbers cannot be confirmed",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "一次性 XLSX 匯入只供系統啟用初期使用；日常仍須逐名建立員工檔案",
                "本版本不改動 Payroll 計算規則，範本導出後仍須由 HR 核對",
            ],
            "zh-Hans": [
                "一次性 XLSX 导入只供系统启用初期使用；日常仍须逐名建立员工档案",
                "本版本不改动 Payroll 计算规则，模板导出后仍须由 HR 核对",
            ],
            "en": [
                "One-time XLSX import is for initial setup only; daily onboarding remains profile-by-profile",
                "Payroll calculation rules are unchanged and HR must still review every exported workbook",
            ],
        },
    },
    {
        "version": "V0.0.3",
        "date": "2026-07-21",
        "title": {
            "zh-Hant": "E-CALL 考勤及 Payroll 規則",
            "zh-Hans": "E-CALL 考勤及 Payroll 规则",
            "en": "E-CALL attendance and payroll rules",
        },
        "features": {
            "zh-Hant": [
                "考勤項目行新增大 E-CALL 及普通 E-CALL 次數",
                "大 E-CALL 每次按適用的一天薪率計算；普通 E-CALL 每次 HKD 400",
                "本期 E-CALL 計入薪金，上月尾實際 E-CALL 進入多付／少付補差",
                "Payroll 範本及考勤／Payroll 報表新增 E-CALL 欄位",
                "登入後可直接查看與目前版本同步的 HR 操作指南",
                "附件及考勤 PDF 以 SHA-256 提示完全相同的文件，經 HR 確認後才替換",
            ],
            "zh-Hans": [
                "考勤项目行新增大 E-CALL 及普通 E-CALL 次数",
                "大 E-CALL 每次按适用的一天薪率计算；普通 E-CALL 每次 HKD 400",
                "本期 E-CALL 计入薪金，上月底实际 E-CALL 进入多付／少付补差",
                "Payroll 模板及考勤／Payroll 报表新增 E-CALL 字段",
                "登录后可直接查看与当前版本同步的 HR 操作指南",
                "附件及考勤 PDF 以 SHA-256 提示完全相同的文件，经 HR 确认后才替换",
            ],
            "en": [
                "Attendance project rows record Large and ordinary E-CALL counts",
                "Each Large E-CALL uses one applicable daily rate; each ordinary E-CALL adds HKD 400",
                "Current E-CALL is paid now and prior-tail actuals enter overpay or underpay reconciliation",
                "Payroll templates and attendance/payroll reports include E-CALL",
                "Signed-in users can view the version-aligned HR user guide",
                "SHA-256 detects identical employee documents and attendance PDFs before HR confirms replacement",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "現有 V1 資料庫可非破壞性自動加欄，無需再次重建資料庫",
                "Payroll 頁常駐顯示 E-CALL 計算及月尾預估規則",
            ],
            "zh-Hans": [
                "现有 V1 数据库可非破坏性自动加字段，无需再次重建数据库",
                "Payroll 页常驻显示 E-CALL 计算及月底预估规则",
            ],
            "en": [
                "Existing V1 databases receive a non-destructive additive upgrade",
                "The Payroll page permanently displays E-CALL and tail-forecast rules",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "E-CALL 次數由 HR 按考勤 PDF 備註人工錄入，暫不使用 OCR",
                "本月 21 日至月底預估不假設 E-CALL，待下月收到實際考勤後補差",
            ],
            "zh-Hans": [
                "E-CALL 次数由 HR 按考勤 PDF 备注人工录入，暂不使用 OCR",
                "本月 21 日至月底预估不假设 E-CALL，待下月收到实际考勤后补差",
            ],
            "en": [
                "HR enters E-CALL counts manually from PDF remarks; OCR is not used",
                "The current tail forecast assumes no E-CALL and reconciles actuals next month",
            ],
        },
    },
    {
        "version": "V0.0.2",
        "date": "2026-07-16",
        "title": {
            "zh-Hant": "員工檔案、考勤及 Payroll 核心流程重構",
            "zh-Hans": "员工档案、考勤及 Payroll 核心流程重构",
            "en": "Employee records, attendance and payroll workflow redesign",
        },
        "features": {
            "zh-Hant": [
                "以永久員工檔案為唯一主資料，先建檔再補資料或附件",
                "多身份證件、證件與 VISA、學歷技能、任職及薪酬歷史",
                "每人每月一份考勤 PDF 的三區人工錄入工作台",
                "本月 1–20 日、上月 21 日至月尾補差及月尾預估 Payroll",
                "三份 Payroll 範本、合同 DOCX package、報表與附件一鍵打包",
            ],
            "zh-Hans": [
                "以永久员工档案为唯一主资料，先建档再补资料或附件",
                "多身份证件、证件与 VISA、学历技能、任职及薪酬历史",
                "每人每月一份考勤 PDF 的三区人工录入工作台",
                "本月 1–20 日、上月 21 日至月尾补差及月尾预估 Payroll",
                "三份 Payroll 模板、合同 DOCX package、报表与附件一键打包",
            ],
            "en": [
                "Permanent employee profiles are the single source of truth",
                "Multiple identities, credentials, VISA, qualifications, employment and salary history",
                "Three-panel manual attendance PDF capture",
                "Payroll with days 1–20 actuals, prior-tail reconciliation and current-tail forecast",
                "Three payroll templates, editable contract packages, reports and attachment bundles",
            ],
        },
        "improvements": {
            "zh-Hant": [
                "移除 OCR 作為主流程；附件預覽和人工核對不再受識別率影響",
                "新增員工只保留一個最小建檔入口",
                "基礎資料不再要求 HR 理解內部 code，項目 code 只保留業務用途",
                "三語介面改用明確翻譯 key，不翻譯員工實際資料",
                "合同年假與通知期分開帶入範本，避免互相覆蓋",
                "員工檔案分頁與手機導航完成實際瀏覽器修正",
            ],
            "zh-Hans": [
                "移除 OCR 作为主流程；附件预览和人工核对不再受识别率影响",
                "新增员工只保留一个最小建档入口",
                "基础资料不再要求 HR 理解内部 code，项目 code 只保留业务用途",
                "三语界面改用明确翻译 key，不翻译员工实际资料",
                "合同年假与通知期分开带入模板，避免互相覆盖",
                "员工档案分页与手机导航完成实际浏览器修正",
            ],
            "en": [
                "OCR is removed from the primary workflow; filing works independently of recognition quality",
                "Employee onboarding now has one minimal create entry",
                "Reference-data codes are hidden from HR except meaningful project codes",
                "The trilingual UI uses explicit translation keys and leaves business data unchanged",
                "Contract annual leave and notice periods are populated independently",
                "Employee tabs and mobile navigation were corrected through browser QA",
            ],
        },
        "limitations": {
            "zh-Hant": [
                "E-call、請假審批及複雜政策引擎未納入 V1",
                "日工月尾預估先按星期一至六，法定假日曆仍需 HR 於下月實際考勤補差",
                "遣散費、長期服務金及代通知金只作參考，必須由 HR 按勞工處工具核對",
            ],
            "zh-Hans": [
                "E-call、请假审批及复杂政策引擎未纳入 V1",
                "日工月尾预估先按星期一至六，法定假日历仍需 HR 于下月实际考勤补差",
                "遣散费、长期服务金及代通知金只作参考，必须由 HR 按劳工处工具核对",
            ],
            "en": [
                "E-call, leave approval and complex policy engines are outside V1",
                "Daily-worker tail forecasts use Monday to Saturday until a statutory-holiday calendar is added",
                "Termination entitlements are reference estimates and require HR verification",
            ],
        },
    },
    {
        "version": "V0.0.1",
        "date": "2026-07-13",
        "title": {
            "zh-Hant": "早期測試版",
            "zh-Hans": "早期测试版",
            "en": "Early test build",
        },
        "features": {
            "zh-Hant": ["早期員工、附件、OCR intake 及 Payroll 測試頁。"],
            "zh-Hans": ["早期员工、附件、OCR intake 及 Payroll 测试页。"],
            "en": ["Early employee, attachment, OCR intake and payroll test screens."],
        },
        "improvements": {
            "zh-Hant": ["已由 V0.0.2 的員工檔案優先流程取代。"],
            "zh-Hans": ["已由 V0.0.2 的员工档案优先流程取代。"],
            "en": ["Superseded by the V0.0.2 profile-first workflow."],
        },
        "limitations": {
            "zh-Hant": ["此版本資料只供測試，不作遷移。"],
            "zh-Hans": ["此版本资料只供测试，不作迁移。"],
            "en": ["Test data from this release is not migrated."],
        },
    },
]


CURRENT_VERSION = RELEASES[0]["version"]

# The next published release follows the current version without skipping.
NEXT_VERSION = "V0.7.8"
