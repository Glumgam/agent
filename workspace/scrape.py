import requests
from bs4 import BeautifulSoup

url = 'https://example.com/biz/ramen'
response = requests.get(url, verify=False)
soup = BeautifulSoup(response.text, 'html.parser')
h1_tag = soup.find('h1').text
p_tags = [p.text for p in soup.find_all('p')]
print(f'h1: {h1_tag}')
for i, p in enumerate(p_tags):
    print(f'p{i+1}: {p}')