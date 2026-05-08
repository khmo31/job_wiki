import requests
r = requests.post('http://127.0.0.1:5000/api/analyze', json={'profile':'테스트 프로필'})
print('status', r.status_code)
print(r.headers)
print(r.text[:2000])
