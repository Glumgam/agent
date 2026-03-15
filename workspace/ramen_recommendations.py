import requests
from bs4 import BeautifulSoup

def get_ramen_recommendations():
    url = 'https://example.com/biz/ramen'  # ラーメン屋の検索ページを指定
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    ramen_list = soup.find_all('div', class_='ramen-item')[:5]  # 最初の5件を取得
    return [item.find('h2').text for item in ramen_list]

if __name__ == '__main__':
    recommendations = get_ramen_recommendations()
    print(recommendations)
