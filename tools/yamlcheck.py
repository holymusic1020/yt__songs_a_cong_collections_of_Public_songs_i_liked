import sys
t = open('.github/workflows/publish.yml').read()
assert '\t' not in t, 'TAB found'
for k in ['MULTIPOST', 'FB_PAGE_ID', 'FB_PAGE_TOKEN']:
    assert k + ':' in t, k
print('sanity OK (no tabs, 3 keys present)')
