const {pdfBytes} = require('./pdf_fixture.cjs');
/* Run against tests/profile_workspace_preview.py only. Synthetic localhost fixtures. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = 'http://127.0.0.1:8766';
(async () => {
  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  const page = await browser.newPage({viewport: {width: 1440, height: 1050}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  let dialogs = 0, accept = false;
  page.on('dialog', async d => { dialogs++; await (accept ? d.accept() : d.dismiss()); });
  let passed = 0;
  const check = async (name, fn) => { await fn(); passed++; console.log('PASS ' + name); };
  try {
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill('admin');
    await page.locator('[name=password]').fill('test-admin-password');
    await Promise.all([page.waitForURL(u => u.pathname !== '/login'), page.locator('button[type=submit]').click()]);
    await page.goto(base + '/employees/1?tab=personal');
    await page.waitForSelector('[data-profile-workspace]', {state: 'attached'});
    const personal = page.locator('#edit-personal-dialog');
    let originalAddress = '';
    await check('unchanged Cancel does not prompt', async () => {
      await page.locator('[data-dialog-open=edit-personal-dialog]').first().click();
      originalAddress = await personal.locator('[name=residential_address]').inputValue();
      await personal.locator('[data-dialog-close]').last().click();
      assert.equal(dialogs, 0);
    });
    await check('cancelled discard retains form; accepted discard resets it', async () => {
      await page.locator('[data-dialog-open=edit-personal-dialog]').first().click();
      await personal.locator('[name=residential_address]').fill('Unsaved QA address');
      await personal.locator('[data-dialog-close]').last().click();
      assert.equal(await personal.getAttribute('open'), '');
      assert.equal(await personal.locator('[name=residential_address]').inputValue(), 'Unsaved QA address');
      accept = true;
      await personal.locator('[data-dialog-close]').last().click();
      assert.equal(await personal.getAttribute('open'), null);
      assert.equal(await personal.locator('[name=residential_address]').inputValue(), originalAddress);
      accept = false;
    });
    await check('failed save retains input; retry saves with the original success message', async () => {
      await page.locator('[data-dialog-open=edit-personal-dialog]').first().click();
      await personal.locator('[name=residential_address]').fill('Saved QA address');
      const endpoint = await personal.locator('form').getAttribute('action');
      await page.route('**' + endpoint, route => route.fulfill({status: 422, contentType: 'application/json', body: JSON.stringify({errors: ['測試欄位錯誤']})}));
      await personal.locator('button[type=submit]').click();
      await personal.locator('[data-save-error]').waitFor();
      assert.equal(await personal.locator('[name=residential_address]').inputValue(), 'Saved QA address');
      await page.unroute('**' + endpoint);
      await Promise.all([page.waitForNavigation(), personal.locator('button[type=submit]').click()]);
      await page.locator('.flash-success').waitFor({timeout: 10000});
      await page.locator('[data-dialog-open=edit-personal-dialog]').first().click();
      assert.equal(await personal.locator('[name=residential_address]').inputValue(), 'Saved QA address');
      await personal.locator('[data-dialog-close]').last().click();
    });
    await check('Escape respects unsaved changes and restoring the old value removes the warning', async () => {
      await page.locator('[data-dialog-open=edit-personal-dialog]').first().click();
      const input = personal.locator('[name=residential_address]');
      const old = await input.inputValue();
      await input.fill('Escape QA draft');
      const before = dialogs;
      await page.keyboard.press('Escape');
      assert.equal(dialogs, before + 1);
      assert.equal(await personal.getAttribute('open'), '');
      await input.fill(old);
      await page.keyboard.press('Escape');
      assert.equal(await personal.getAttribute('open'), null);
      assert.equal(dialogs, before + 1);
    });
    await check('workweek/date impact is contextual and disappears when reverted', async () => {
      await page.locator('[data-tab=employment]').click();
      const opener = page.locator('[data-dialog-open=add-assignment-dialog]');
      await opener.click();
      const dialog = page.locator('#add-assignment-dialog');
      const select = dialog.locator('[name=workweek_days]');
      const old = await select.inputValue();
      assert.equal(await dialog.locator('[data-impact-note]').count(), 0);
      await select.selectOption(old === '6' ? '5' : '6');
      assert.ok((await dialog.locator('[data-impact-note]').textContent()).includes('已匯出的工資表'));
      await select.selectOption(old);
      assert.equal(await dialog.locator('[data-impact-note]').count(), 0);
      await dialog.locator('[data-dialog-close]').last().click();
    });
    await check('money formatting without a value change does not trigger discard', async () => {
      await page.locator('[href="#employment-status"]').click();
      await page.locator('[data-dialog-open=termination-editor-dialog]').first().click();
      const dialog = page.locator('#termination-editor-dialog');
      const count = dialogs;
      await dialog.locator('[name=average_wage]').focus();
      await dialog.locator('[data-dialog-close]').last().click();
      assert.equal(dialogs, count);
      assert.equal(await dialog.getAttribute('open'), null);
    });
    await check('history cells share row boundaries and show one effective date at three widths', async () => {
      await page.locator('[data-tab=employment]').click();
      const table = page.locator('.change-history-table');
      const historic = table.locator('tbody > tr').filter({has: page.locator('.history-effective-end')});
      assert.equal((await historic.locator(':scope > td').first().innerText()).trim(), '2022-09-19');
      assert.ok((await historic.locator('.history-effective-end').innerText()).includes('2025-12-31'));
      for (const width of [1024, 1440, 1920]) {
        await page.setViewportSize({width, height: 1050});
        const measurements = await table.locator('tbody > tr').evaluateAll(rows => rows.map(row =>
          [...row.cells].map(cell => ({display: getComputedStyle(cell).display,
            top: cell.getBoundingClientRect().top, bottom: cell.getBoundingClientRect().bottom}))));
        for (const cells of measurements) {
          assert.equal(cells.length, 6);
          assert.ok(cells.every(cell => cell.display === 'table-cell'));
          assert.ok(Math.max(...cells.map(cell => cell.top)) - Math.min(...cells.map(cell => cell.top)) < 1);
          assert.ok(Math.max(...cells.map(cell => cell.bottom)) - Math.min(...cells.map(cell => cell.bottom)) < 1);
        }
      }
      assert.ok(await page.evaluate(() => {
        const tabs = document.querySelector('.system-tabs');
        const bar = document.querySelector('.topbar');
        return tabs && bar && tabs.scrollWidth <= tabs.clientWidth + 1 && bar.scrollWidth <= bar.clientWidth + 1;
      }));
      await page.setViewportSize({width: 1440, height: 1050});
      fs.mkdirSync('tmp', {recursive: true});
      await table.screenshot({path: 'tmp/profile-history-alignment.png'});
    });
    await check('evidence supplement dialog opens from history table without inline overflow', async () => {
      await page.locator('[data-tab=employment]').click();
      const trigger = page.locator('[data-dialog-open^="supplement-employment-evidence-"]').first();
      const targetId = await trigger.getAttribute('data-dialog-open');
      await trigger.click();
      const dialog = page.locator('#' + targetId);
      assert.equal(await dialog.getAttribute('open'), '');
      await dialog.locator('[data-dialog-close]').last().click();
      assert.equal(await dialog.getAttribute('open'), null);
    });
    await check('real sick-leave upload error lists formats inside the original dialog', async () => {
      await page.locator('[data-tab=leave]').click();
      await page.locator('[data-dialog-open=add-leave-dialog]').click();
      const dialog = page.locator('#add-leave-dialog');
      await dialog.locator('[name=leave_type]').selectOption('sick');
      await dialog.locator('[name=start_date]').fill('2026-09-09');
      await dialog.locator('[name=end_date]').fill('2026-09-09');
      await dialog.locator('[name=evidence]').setInputFiles({name: 'invalid.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('not an image')});
      await dialog.locator('button[type=submit]').click();
      await dialog.locator('[data-save-error]').waitFor();
      const message = await dialog.locator('[data-save-error]').textContent();
      for (const ext of ['.pdf', '.jpg', '.jpeg', '.png', '.docx', '.xlsx']) assert.ok(message.includes(ext));
      assert.ok(message.includes('未通過格式驗證'));
      assert.equal(await dialog.locator('[name=evidence]').evaluate(e => e.files[0].name), 'invalid.jpg');
      assert.equal(await dialog.locator('[name=start_date]').inputValue(), '2026-09-09');
      accept = true;
      await dialog.locator('[data-dialog-close]').last().click();
      accept = false;
    });
    await check('leave workspace retains errors and refreshes same-page success exactly once', async () => {
      await page.goto(base + '/annual-leave?employee_id=1&year=2026');
      await page.getByRole('button', {name: '新增請假', exact: true}).click();
      const dialog = page.locator('#add-leave-dialog');
      await dialog.locator('[name=start_date]').fill('2026-09-22');
      await dialog.locator('[name=end_date]').fill('2026-09-22');
      await dialog.locator('[name=evidence]').setInputFiles({name: 'bad.pdf', mimeType: 'application/pdf', buffer: Buffer.from('not PDF')});
      await dialog.locator('button[type=submit]').click();
      await dialog.locator('[data-save-error]').waitFor();
      assert.equal(await dialog.locator('[name=start_date]').inputValue(), '2026-09-22');
      assert.equal(await dialog.locator('[name=evidence]').evaluate(e => e.files[0].name), 'bad.pdf');
      await dialog.locator('[name=evidence]').setInputFiles({name: 'recovered.pdf', mimeType: 'application/pdf', buffer: pdfBytes('QA')});
      await Promise.all([page.waitForNavigation(), dialog.locator('button[type=submit]').click()]);
      assert.equal(await page.locator('dialog[open]').count(), 0);
      assert.equal(await page.locator('.leave-history-table tbody tr').filter({hasText: 'recovered.pdf'}).count(), 1);
    });
    await check('file error and uncertain response retain selected attachment', async () => {
      await page.goto(base + '/employees/1/documents/new?upload_type=cv');
      const form = page.locator('main form[method=post]');
      await form.locator('[name=file]').setInputFiles({name: 'qa.pdf', mimeType: 'application/pdf', buffer: pdfBytes('QA')});
      await form.locator('[name=title]').fill('QA retained title');
      const mask = '**/employees/1/documents/new?upload_type=cv';
      await page.route(mask, route => route.request().method() === 'POST' ? route.fulfill({status: 400, contentType: 'text/html', body: '<div class="flash flash-error">Invalid QA file</div>'}) : route.continue());
      await form.locator('button[type=submit]').click();
      await form.locator('[data-save-error]').waitFor();
      assert.equal(await form.locator('[name=file]').evaluate(e => e.files[0].name), 'qa.pdf');
      assert.equal(await form.locator('[name=title]').inputValue(), 'QA retained title');
      await page.unroute(mask);
      await page.route(mask, route => route.abort());
      await form.locator('button[type=submit]').click();
      await page.waitForFunction(() => document.querySelector('[data-save-error]')?.textContent.includes('未能確認'));
      assert.equal(await form.locator('[name=file]').evaluate(e => e.files.length), 1);
      await page.unroute(mask);
      accept = true;
      await page.locator('main .page-head a').click();
      accept = false;
    });
    await check('category filters preserve actions and hide optional empty categories without red warnings', async () => {
      const lib = page.locator('[data-document-library]');
      await lib.locator('[data-document-filter=staff_record]').click();
      assert.equal(await lib.locator('tr[data-document-category]:visible').count(), 1);
      assert.equal(await lib.locator('.document-file-details[open]').count(), 0);
      await lib.locator('[data-document-empty-toggle]').click();
      await lib.locator('[data-document-filter=cv]').click();
      assert.equal(await lib.locator('tr[data-document-category]:visible').count(), 0);
      assert.ok(await lib.locator('[data-library-empty]').isVisible());
      await lib.locator('[data-document-filter=""]').click();
      assert.equal(await lib.locator('.doc-card.missing').count(), 0);
      assert.ok(await lib.locator('.document-link').first().isVisible());
      fs.mkdirSync('tmp', {recursive: true});
      await page.screenshot({path: 'tmp/profile-workspace-library.png', fullPage: true});
    });
    await check('identical upload uses existing confirmation and cancel does not mutate records', async () => {
      const href = await page.locator('[data-document-library] tr[data-document-category=staff_record] a[href$="/download"]').first().getAttribute('href');
      const response = await page.request.get(base + href);
      const buffer = await response.body();
      await page.goto(base + '/employees/1/documents/new?upload_type=staff_record');
      await page.locator('main [name=file]').setInputFiles({name: 'duplicate.pdf', mimeType: 'application/pdf', buffer});
      await page.locator('main button[type=submit]').click();
      await page.locator('input[name=duplicate_token]').waitFor({state: 'attached'});
      await Promise.all([page.waitForNavigation(), page.locator('button[name=action][value=cancel]').click()]);
      await page.goto(base + '/employees/1?tab=documents');
      assert.equal(await page.locator('tr[data-document-category=staff_record]').count(), 1);
    });
    assert.deepEqual(errors, []);
    console.log(`${passed} browser scenarios passed; no page errors.`);
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
