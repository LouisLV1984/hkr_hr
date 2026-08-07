RELEASES = [
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
            ],
            "zh-Hans": [
                "登记年假可分别指定使用旧年假及 2024 起年假；后者自动先扣最早到期且仍有效的年度",
                "离职结算页常驻显示假期补薪、2025-05-01 转制、款额上限及 MPF 抵销规则",
                "Final Payment 使用清理后的正式模板，保留基本工资、OT、假日、总额及实发金额 Excel 公式",
            ],
            "en": [
                "A leave entry can split usage between legacy and post-2024 leave; post-2024 leave uses the oldest valid balance first",
                "Final Payment keeps leave-pay, 2025-05-01 transition, payment-cap and MPF-offset rules visible on the page",
                "The cleaned Final Payment template retains Excel formulas for basic pay, OT, holidays, totals and actual payment",
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
NEXT_VERSION = "V0.1.5"
