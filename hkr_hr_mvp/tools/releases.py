RELEASES = [
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
                "離職年度年假按含頭尾兩日的當年在職日數除以 365／366 自動折算；超用先抵扣其他可用年假，仍不足部分在 Final Payment 追扣。年假補薪日薪率改為前 12 個月工資合計除以 365，並顯示找到的 Payroll 月數及 HR 核實提示。",
                "假期與工傷新增姓名／員工編號搜尋，支援中文繁簡體及英文姓名；考勤聯動框分別說明日工的實際出勤日數是唯一計薪依據、不會再因無薪假重複扣薪，而月工／OFFICE 的無薪假只按假期記錄扣減一次。",
                "工傷、離職結算、MPF、病假／無薪假及各類補貼的計算規則在相應頁面常駐顯示；工傷計薪基礎預填合約底薪，並提示 HR 按意外發生時每月收入核實。",
                "工傷計薪方式、每月醫療實銷、離職年假折算及 Payroll 結果均保留結構化資料與審計軌跡；資料庫升級採加法式欄位，不覆蓋既有員工記錄。",
            ],
            "zh-Hans": [
                "离职年度年假按含头尾两日的当年在职日数除以 365／366 自动折算；超用先抵扣其他可用年假，仍不足部分在 Final Payment 追扣。年假补薪日薪率改为前 12 个月工资合计除以 365，并显示找到的 Payroll 月数及 HR 核实提示。",
                "假期与工伤新增姓名／员工编号搜索，支持中文繁简体及英文姓名；考勤联动框分别说明日工的实际出勤日数是唯一计薪依据、不会再因无薪假重复扣薪，而月工／OFFICE 的无薪假只按假期记录扣减一次。",
                "工伤、离职结算、MPF、病假／无薪假及各类补贴的计算规则在相应页面常驻显示；工伤计薪基础预填合同底薪，并提示 HR 按意外发生时每月收入核实。",
                "工伤计薪方式、每月医疗实销、离职年假折算及 Payroll 结果均保留结构化资料与审计轨迹；数据库升级采用加法式栏位，不覆盖既有员工记录。",
            ],
            "en": [
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
NEXT_VERSION = "V0.2.9"
