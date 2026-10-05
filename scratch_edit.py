p = 'tests_browser/test_booked.py'
s = open(p, encoding='utf-8').read()
def sub(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)
sub('def test_sos_opens_the_emergency_sheet_with_every_call_link(imported_page, base_url, viewport):\n    page = imported_page(viewport=viewport)\n',
    'def test_sos_opens_the_emergency_sheet_with_every_call_link(imported_page, base_url, viewport, monkeypatch):\n    monkeypatch.setenv("GITAWAY_VAPID_PUBLIC", "BPublicKey"), monkeypatch.setenv("GITAWAY_VAPID_PRIVATE", "p"), monkeypatch.setenv("GITAWAY_VAPID_SUBJECT", "mailto:a@b.co")\n    page = imported_page(viewport=viewport)\n')
sub('    page.wait_for_url(re.compile(r"/family#this-phone"))\n    expect(page.locator("#this-phone, #morning-plan").first).to_be_attached()',
    '    page.wait_for_url(re.compile(r"/family#morning-plan"))\n    expect(page.locator("#morning-plan #tp-morning")).to_be_visible()')
open(p, 'w', encoding='utf-8').write(s)
