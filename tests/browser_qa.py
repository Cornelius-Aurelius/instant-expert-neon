from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
# Self-contained layout harness. It injects exactly the published stylesheet and scripts.
html=(ROOT/'index.html').read_text()
css=(ROOT/'styles.css').read_text(); core=(ROOT/'core.js').read_text(); app=(ROOT/'app.js').read_text()


errors=[]
def serve(route):
    url=route.request.url
    if url.endswith('/styles.css'): route.fulfill(status=200,content_type='text/css',body=css)
    elif url.endswith('/core.js'): route.fulfill(status=200,content_type='application/javascript',body=core)
    elif url.endswith('/app.js'): route.fulfill(status=200,content_type='application/javascript',body=app)
    elif url.endswith('.svg'): route.fulfill(status=200,content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg"/>')
    else:route.fulfill(status=200,content_type='text/html',body=html)

html=html.replace('<link rel="stylesheet" href="styles.css">','<style>'+css+'</style>')
html=html.replace('<script defer src="core.js"></script><script defer src="app.js"></script>','').replace('</body>','<script>'+core+'</script><script>'+app+'</script></body>')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    for width in [280,320,375,430,768,1024,1440]:
        page=browser.new_page(viewport={"width":width,"height":800},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('about:blank');page.set_content(html,wait_until='load')
        page.wait_for_timeout(150)
        metrics=page.evaluate('({width:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,docHeight:document.documentElement.scrollHeight,heading:document.querySelector("h1")?.textContent,ready:!!window.ExpertCore})')
        assert metrics['width'] <= width+1,(width,metrics)
        assert metrics['ready'],(width,'engine missing')
        if width in [375,1440]:page.screenshot(path=str(ROOT/'tests'/f'screen_{width}.png'),full_page=True)
        print('viewport',width,metrics)
        page.close()
    page=browser.new_page(viewport={"width":390,"height":850})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('about:blank')
    # about:blank blocks persistent storage: mock browser-local storage for interaction test.
    page.evaluate('''() => {let memory={};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem(k){return memory[k]??null},setItem(k,v){memory[k]=String(v)},removeItem(k){delete memory[k]}}})}''')
    page.set_content(html,wait_until='load')
    page.get_by_role('button',name='01 · BUSINESS Is my product idea worth testing?').click()
    assert page.locator('#goal').input_value().startswith('Find out')
    page.get_by_role('button',name='Generate decision brief').click()
    assert page.locator('#reportView').is_visible()
    assert 'potential users' in page.locator('#reportEditor').input_value()
    assert 'No option is automatically recommended' in page.locator('#reportEditor').input_value()
    page.locator('#reportEditor').fill('My edited decision brief.')
    page.locator('#saveBtn').click()
    page.locator('#resetBtn').click()
    assert page.locator('#emptyState').is_visible()
    page.locator('#loadBtn').click() if page.locator('#loadBtn').is_visible() else None
    # restore saved draft through a newly generated output
    page.locator('[data-example="technology"]').click();page.locator('#generateBtn').click()
    page.locator('#loadBtn').click()
    assert page.locator('#reportEditor').input_value()=='My edited decision brief.'
    page.locator('#deleteBtn').click()
    assert page.evaluate('localStorage.getItem("instant-expert-neon-draft-v2")') is None
    page.locator('#downloadBtn').click()
    page.locator('#printBtn').click()
    assert page.locator('#printReport').text_content()=='My edited decision brief.'
    page.locator('#resetBtn').click()
    page.locator('#generateBtn').click()
    assert page.locator('#formError').is_visible()
    page.locator('#goal').fill('<img src=x onerror=alert(1)> review a project')
    # Security-sensitive input must become literal text, never HTML.
    page.locator('#context').fill('I have a limited development budget and need a safe project plan')
    page.locator('#generateBtn').click()
    assert page.locator('#reportView').is_visible()
    assert page.locator('#reportSections img').count()==0
    assert len(errors)==0,errors
    print('full interactive workflow passed')
    page.close()
    browser.close()
