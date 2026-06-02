#  Install the Python Requests library:
# `pip install requests`
# import requests

# def send_request():
#     response = requests.get(
#         url='https://app.scrapingbee.com/api/v1',
#         params={
#             'api_key': 'WTB6H8C9IXOP4E11KABV5MU20JWK4DOFXCHM55D4A8HD73J0IAEWG1GVI3PJN3QCS5GE8R1241YASFS8',
#             'url': 'https://www.ebay.com/sch/i.html?_nkw=Hyundai+ioniq+2020',
#             'render_js': 'false'
#         },
#     )
#     print('Response HTTP Status Code: ', response.status_code)
#     print('Response HTTP Response Body: ', response.content)
# send_request()
  


  #  Install the Python Requests library:
# `pip install requests`
import requests

def send_request():
    response = requests.get(
        url='https://app.scrapingbee.com/api/v1',
        params={
            'api_key': 'WTB6H8C9IXOP4E11KABV5MU20JWK4DOFXCHM55D4A8HD73J0IAEWG1GVI3PJN3QCS5GE8R1241YASFS8',
            'url': 'https://hyundai.oempartsonline.com/v-2020-hyundai-ioniq--plug-in-hybrid-se--1-6l-l4-electric-gas/body--bumper-and-components-front',
            'render_js': 'false',
            'ai_query': 'get the part number, part name, price, compatibility list, '
        },
    )
    print('Response HTTP Status Code: ', response.status_code)
    print('Response HTTP Response Body: ', response.content)
send_request()
  