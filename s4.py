import requests
from bs4 import BeautifulSoup

url = "https://flask-ruby-rho.vercel.app/me"
Data = requests.get(url)
Data.encoding = "utf-8"
#print(Data.text)
sp = BeautifulSoup(Data.text, "html.parser")
result=sp.find(id="h2text")
print(result.text)


