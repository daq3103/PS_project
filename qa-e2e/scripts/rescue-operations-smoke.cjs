// Synthetic API/browser contract checks. Never writes to the real shelter database.
const http=require('node:http'),path=require('node:path'),fs=require('node:fs');
const {spawn,spawnSync}=require('node:child_process');
const dockerRuntime=process.env.RESCUE_TEST_DOCKER==='1';
const {chromium,expect}=require('@playwright/test');
const root=path.resolve(__dirname,'../..'),base='http://127.0.0.1:3137',stamp=new Date().toISOString();
const uid='11111111-1111-4111-8111-111111111111',aid='22222222-2222-4222-8222-222222222222';
const publicAnimal={id:aid,code:'BE-QA0001',slug:'miu-qa0001',name:'Miu thử nghiệm',species:'cat',sex:'unknown',age_months:null,story:'Miu đang được chăm sóc và làm quen với môi trường mới.',care_summary:'Thông tin chăm sóc sẽ được trạm xác nhận khi trao đổi.',public_area:'Hà Nội',adoption_state:'not_open',images:[]};
let animal={...publicAnimal,post_id:null,version:1,ownership_hold:false,publication:publicAnimal};
let reports=[],locations=[],events=[],partners=[],shifts=[],messages=[],lastMutation;
const owner={id:uid,full_name:'Chủ trạm thử nghiệm',role:'owner',totp_enabled:true,staff_permissions:[]};
const apiServer=http.createServer(async(req,res)=>{
 const url=new URL(req.url,'http://127.0.0.1:3138'),p=url.pathname;let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};let result=[];
 if(req.method!=='GET')lastMutation={path:p,body,key:req.headers['idempotency-key']};
 if(p.endsWith('/auth/me'))result={user:owner,csrf_token:null,admin_verified:true};
 else if(p.endsWith('/analytics/config'))result={enabled:false};
 else if(p.endsWith('/community/config'))result={enabled:true};
 else if(p.endsWith('/cart'))result={items:[],item_count:0,subtotal:0};
 else if(p.endsWith('/rescue/config'))result={area:'Hà Nội',donations_enabled:false};
 else if(p.endsWith('/rescue/campaigns'))result={enabled:false,campaigns:[]};
 else if(p.endsWith('/rescue/me/workspace'))result={appointments:[],partners,shifts,tasks:[],saved_animals:[],applications:[],consents:[],pledges:[]};
 else if(p.endsWith('/rescue/me/foster-animals'))result=[];
 else if(p.endsWith('/admin/rescue/coordination'))result={appointments:[],partners,shifts,checks:[],pledges:[],needs:[],schedules:[],slots:[],support_threads:[{id:uid,name:owner.full_name}],applications:[],staff:[{id:uid,name:owner.full_name},{id:'44444444-4444-4444-8444-444444444444',name:'Người dự phòng thử nghiệm'}],animals:[animal]};
 else if(p.endsWith('/admin/rescue/recovery-review'))result={gift_order_exceptions:[],unassigned_open_episodes:0,pending_transfer_exceptions:0,as_of:stamp};
 else if(p.endsWith('/admin/rescue/activity-report'))result={period:{start:url.searchParams.get('start'),end_exclusive:url.searchParams.get('end'),as_of:stamp},reports:3,cases:1,intake_episodes:4,distinct_animals:3,currently_in_care:2,currently_fostered:1,outcomes:{adopted:1,returned_owner:1},overdue_tasks:0,care_duration_days_closed:5,return_cohort_30_days:{adoptions:1,returned:0,matured:1,rate:0},trial_visits:1};
 else if(p.endsWith('/admin/rescue/audit'))result=[{id:'audit-qa',created_at:stamp,actor_name:owner.full_name,action_label:'Hồ sơ bé · tạo mới',resource_label:'BE-QA0001',reason:'Đã kiểm tra nguồn tiếp nhận'}];
 else if(p.endsWith('/admin/rescue/contributions'))result={enabled:false,campaigns:[],intents:[],events:[],refunds:[]};
 else if(p.endsWith('/rescue/partners')){const r={...body,id:'55555555-5555-4555-8555-555555555555',status:'pending',version:1};partners.push(r);result=r;}
 else if(p.endsWith('/admin/rescue/shifts')){const r={...body,id:'66666666-6666-4666-8666-666666666666',status:'scheduled',version:1};shifts.push(r);result=r;}
 else if(p.endsWith('/rescue/messages')){if(req.method!=='GET'){messages.push({...body,id:'message-qa',mine:true,sender_name:owner.full_name,created_at:stamp});result={id:'message-qa'};}else result=messages;}
 else if(p.endsWith('/rescue/me/reports'))result=reports;
 else if(p.endsWith('/rescue/reports')){const r={id:'report-qa',code:'TIN-QA0001',status:'new',acknowledged:false,created_at:stamp};reports.push(r);result=r;}
 else if(p.endsWith('/rescue/animals'))result=[publicAnimal];
 else if(p.endsWith('/rescue/animals/miu-qa0001'))result=publicAnimal;
 else if(p.endsWith('/rescue/transparency'))result=[];
 else if(p.endsWith('/admin/rescue/workspace'))result={animals:[animal],locations,tasks:[{id:'task-qa',animal_id:aid,title:'Hỏi thăm gia đình sau nhận nuôi',instructions:'Ghi nhận nhu cầu hỗ trợ từ gia đình.',status:'todo',due_at:stamp}],reports:[],cases:[],staff:[{id:uid,name:owner.full_name}],adoption_posts:[]};
 else if(p.endsWith(`/admin/rescue/animals/${aid}`))result={...animal,episodes:[],events};
 else if(p.endsWith('/admin/rescue/locations')){const l={...body,id:'33333333-3333-4333-8333-333333333333',occupied:0};locations.push(l);result=l;}
 else if(p.endsWith('/care')){const e={...body,id:'event-qa',created_at:stamp};events.push(e);result=e;}
 else if(p.endsWith('/admin/rescue/finance'))result={funds:[{id:'fund-qa',title:'Quỹ chăm sóc thử nghiệm',purpose:'Chăm sóc các bé theo nhu cầu đã xác nhận.',surplus_policy:'Giữ đúng mục đích đã công bố.',confirmed:1000000,settled:1000000,spent:200000,committed:300000,available:500000}],entries:[],expenses:[]};
 res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(result));
});
(async()=>{let app,browser;try{
 await new Promise(r=>apiServer.listen(3138,dockerRuntime?'0.0.0.0':'127.0.0.1',r));
 app=dockerRuntime?spawn('docker',['run','--rm','--name','pethome-rescue-ui-smoke','--memory=256m','--memory-swap=256m','--cpus=1','-p','127.0.0.1:3137:3000','-e','INTERNAL_API_URL=http://host.docker.internal:3138','-e','NODE_OPTIONS=--max-old-space-size=192',process.env.RESCUE_TEST_IMAGE||'pethome-rescue-ui:local'],{stdio:['ignore','pipe','pipe'],windowsHide:true}):spawn(process.execPath,['--max-old-space-size=256','node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3137'],{cwd:path.join(root,'frontend'),env:{...process.env,INTERNAL_API_URL:'http://127.0.0.1:3138'},stdio:['ignore','pipe','pipe'],windowsHide:true});
 app.stderr.on('data',c=>process.stderr.write(c));
 await expect.poll(async()=>{try{return(await fetch(base)).status;}catch{return 0;}},{timeout:60000}).toBe(200);
 browser=await chromium.launch({headless:true});const page=await browser.newPage({locale:"vi-VN",timezoneId:"Asia/Ho_Chi_Minh"});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const shots=path.join(root,'PetHome-screenshots');fs.mkdirSync(shots,{recursive:true});
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:900});
  await page.goto(base+'/tram-cuu-ho/cac-be');await expect(page.getByRole('heading',{name:'Theo dõi các bé tại trạm'})).toBeVisible();
  await page.getByRole('link',{name:/Miu thử nghiệm/}).click();await expect(page.getByRole('heading',{name:'Miu thử nghiệm',exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Nhắn qua Zalo'})).toHaveAttribute('href',/^https:\/\/zalo\.me/);
  await expect(page.getByRole('link',{name:'Nhắn qua Facebook'})).toHaveAttribute('target','_blank');
  await expect(page.getByText('Tuổi ước tính: 0 tháng')).toHaveCount(0);
  await page.evaluate(()=>window.scrollTo({top:0,left:0,behavior:"instant"}));
  await page.screenshot({path:path.join(shots,`rescue-animal-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
 }
 await page.goto(base+'/tram-cuu-ho/bao-tin');
 await page.getByLabel('Thời điểm nhìn thấy',{exact:true}).fill('2026-10-27T08:00');
 await page.getByLabel('Mô tả sự việc',{exact:true}).fill('Có một bé cần người phụ trách kiểm tra và hỗ trợ.');
 await page.locator('input[name="private_location"]').fill('Địa chỉ thử nghiệm tại Hà Nội');
 await page.getByLabel('Số điện thoại hoặc cách liên hệ lại',{exact:true}).fill('0900000000');await page.getByRole('checkbox').check();
 await page.getByRole('button',{name:'Gửi tin cho trạm',exact:true}).click();await expect(page.getByRole('status')).toContainText('TIN-QA0001');
 expect(lastMutation.body.consent).toBe(true);expect(lastMutation.key).toBeTruthy();
 await page.goto(base+'/admin/rescue');await expect(page.getByRole('heading',{name:'Chăm sóc & tiếp nhận',exact:true})).toBeVisible();
 await page.getByRole('button',{name:/Miu thử nghiệm/}).click();
 const careForm=page.locator('form').filter({has:page.getByRole('heading',{name:'Ghi nhật ký chăm sóc',exact:true})});
 await careForm.getByLabel('Nội dung ghi nhận',{exact:true}).fill('Bé đã ăn và được theo dõi trong ca hôm nay.');
 await careForm.getByRole('button',{name:'Lưu thông tin',exact:true}).click();await expect(careForm.getByRole('status')).toContainText('Đã lưu');
 expect(lastMutation.path).toContain('/care');expect(lastMutation.body.note).toContain('Bé đã ăn');
 await page.evaluate(()=>window.scrollTo({top:0,left:0,behavior:"instant"}));await page.screenshot({path:path.join(shots,'rescue-desk-390.png'),fullPage:true});
 await page.getByRole('button',{name:'Nơi chăm sóc',exact:true}).click();
 const locForm=page.locator('form').filter({has:page.getByRole('heading',{name:'Nơi chăm sóc / nhà chăm sóc tạm',exact:true})});
 await locForm.getByLabel('Tên nơi chăm sóc',{exact:true}).fill('Nhà tạm thử nghiệm');await locForm.getByLabel('Số bé tối đa đã được trạm xác nhận',{exact:true}).fill('2');
 await locForm.getByRole('button',{name:'Lưu thông tin',exact:true}).click();await expect(locForm.getByRole('status')).toContainText('Đã lưu');
 expect(lastMutation.body.available_from).toBeUndefined();expect(lastMutation.body.available_until).toBeUndefined();
 await page.goto(base+'/admin/rescue/finance');await expect(page.getByRole('heading',{name:'Sổ quỹ cứu hộ',exact:true})).toBeVisible();
 await expect(page.getByText('Còn có thể dùng',{exact:true})).toBeVisible();await page.screenshot({path:path.join(shots,'rescue-finance-390.png'),fullPage:true});
 await page.goto(base+'/tram-cuu-ho/minh-bach');await expect(page.getByText(/Chưa có báo cáo được công bố/)).toBeVisible();
 await page.goto(base+'/account/rescue');await expect(page.getByRole('heading',{name:'Đồng hành của tôi',exact:true})).toBeVisible();
 const support=page.locator('form').filter({has:page.getByLabel('Lời nhắn',{exact:true})});
 await support.getByLabel('Lời nhắn',{exact:true}).fill('Tôi muốn trao đổi với trạm về chăm sóc tạm tại Hà Nội.');await support.getByRole('button',{name:'Gửi lời nhắn',exact:true}).click();await expect(page.getByText('Tôi muốn trao đổi với trạm về chăm sóc tạm tại Hà Nội.',{exact:true})).toBeVisible();
 const partnerForm=page.locator('form').filter({has:page.getByRole('heading',{name:'Đăng ký hỗ trợ trạm tại Hà Nội',exact:true})});
 await partnerForm.getByLabel('Họ tên',{exact:true}).fill('Người đồng hành thử nghiệm');await partnerForm.getByLabel('Điện thoại / cách liên hệ',{exact:true}).fill('0900000000');await partnerForm.getByLabel('Khu vực có thể hỗ trợ',{exact:true}).fill('Hà Nội');await partnerForm.getByLabel('Điều kiện, kinh nghiệm và phương án dự phòng',{exact:true}).fill('Có phòng riêng và người hỗ trợ dự phòng khi bận.');await partnerForm.locator('input[name="capacity"]').fill('2');await partnerForm.locator('input[name="available_from"]').fill('2026-10-28T08:00');await partnerForm.locator('input[name="available_until"]').fill('2026-11-28T08:00');await partnerForm.getByRole('checkbox').check();await partnerForm.getByRole('button',{name:'Lưu thông tin',exact:true}).click();await expect(partnerForm.getByRole('status')).toContainText('Đã lưu');expect(lastMutation.body.available_from).toBe('2026-10-28T01:00:00.000Z');
 await page.evaluate(()=>window.scrollTo({top:0,left:0,behavior:'instant'}));await page.screenshot({path:path.join(shots,'rescue-portal-390.png'),fullPage:true});
 await page.goto(base+'/admin/rescue/coordination');await expect(page.getByRole('heading',{name:'Điều phối trạm',exact:true})).toBeVisible();await page.getByRole('button',{name:'Ca trực',exact:true}).click();
 const shiftForm=page.locator('form').filter({has:page.getByRole('heading',{name:'Phân công ca trực',exact:true})});await shiftForm.getByLabel('Người dự phòng khác người trực',{exact:true}).selectOption('44444444-4444-4444-8444-444444444444');await shiftForm.locator('input[name="starts_at"]').fill('2026-10-28T08:00');await shiftForm.locator('input[name="ends_at"]').fill('2026-10-28T12:00');await shiftForm.getByLabel('Công việc, đầu mối và phạm vi hỗ trợ',{exact:true}).fill('Kiểm tra tin chưa tiếp nhận và ghi bàn giao ca.');await shiftForm.getByRole('button',{name:'Lưu thông tin',exact:true}).click();await expect(shiftForm.getByRole('status')).toContainText('Đã lưu');expect(lastMutation.body.starts_at).toBe('2026-10-28T01:00:00.000Z');
 await page.evaluate(()=>window.scrollTo({top:0,left:0,behavior:'instant'}));await page.screenshot({path:path.join(shots,'rescue-coordination-390.png'),fullPage:true});expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
 await page.goto(base+'/admin/rescue/activity');await expect(page.getByRole('heading',{name:'Báo cáo hoạt động trạm',exact:true})).toBeVisible();
 const reportForm=page.locator('form').filter({has:page.getByRole('heading',{name:'Chọn kỳ báo cáo',exact:true})});await reportForm.getByLabel('Từ thời điểm',{exact:true}).fill('2026-10-01T00:00');await reportForm.getByLabel('Đến thời điểm (không bao gồm)',{exact:true}).fill('2026-11-01T00:00');await reportForm.getByRole('button',{name:'Lưu thông tin',exact:true}).click();await expect(page.getByRole('table').getByText('Chỉ số',{exact:true})).toBeVisible();const downloading=page.waitForEvent('download');await page.getByRole('button',{name:'Tải báo cáo tổng hợp',exact:true}).click();const download=await downloading;expect(download.suggestedFilename()).toBe('bao-cao-hoat-dong-tram.csv');await page.evaluate(()=>window.scrollTo({top:0,left:0,behavior:'instant'}));await page.screenshot({path:path.join(shots,'rescue-activity-390.png'),fullPage:true});
 await page.goto(base+'/admin/rescue/audit');await expect(page.getByRole('heading',{name:'Lịch sử thay đổi của trạm',exact:true})).toBeVisible();await expect(page.getByText('Hồ sơ bé · tạo mới · BE-QA0001',{exact:true})).toBeVisible();
 expect(errors).toEqual([]);console.log('PASS: profile, contact, report, private chat, foster registration, care, shifts, Vietnam timezone, finance, activity CSV, audit and responsive layout');
}catch(error){if(browser){const failedPage=browser.contexts()[0]?.pages()[0];if(failedPage){console.error("Failure page:",failedPage.url());console.error((await failedPage.locator("body").innerText()).slice(0,6000));console.error(await failedPage.locator("form").evaluateAll(forms=>forms.map(form=>({valid:form.checkValidity(),fields:[...form.querySelectorAll("input,select,textarea")].map(input=>({name:input.name,value:input.value,valid:input.validity.valid,message:input.validationMessage}))}))));await failedPage.screenshot({path:path.join(root,"PetHome-screenshots/rescue-qa-failure.png"),fullPage:true});}}throw error;}finally{if(browser)await browser.close();if(dockerRuntime)spawnSync('docker',['stop','--time','3','pethome-rescue-ui-smoke'],{stdio:'ignore',windowsHide:true});if(app&&app.exitCode===null){const done=new Promise(r=>app.once('exit',r));app.kill();await done;}await new Promise(r=>apiServer.close(r));}})().catch(e=>{console.error(e);process.exitCode=1;});
