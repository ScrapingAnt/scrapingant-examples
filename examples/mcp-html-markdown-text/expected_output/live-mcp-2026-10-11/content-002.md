# Ant Supply catalogue (fixture for pandas.read_html)

Eleven tables, each built to trigger one read_html behaviour.

## 1\. simple

Name| Age| City  
---|---|---  
Ada| 36| London  
Grace| 45| Arlington  
Linus| 28| Helsinki  
  
## 2\. prices (thead, thousands separators, currency, percent)

Product| Price| Units sold| Share  
---|---|---|---  
Ant Farm Deluxe| $1,234.50| 12,345| 45.5%  
Ant Farm Mini| $99.00| 1,020| 3.8%  
Magnifier| $12.25| 987,654| 50.7%  
  
## 3\. two-row header (colspan in thead)

Region| 2025| 2026  
---|---|---  
Q1| Q2| Q1| Q2  
North| 10| 12| 14| 16  
South| 7| 8| 9| 11  
  
## 4\. spans in the body

Group| Item| Qty  
---|---|---  
Tools| Tweezers| 4  
Brush| 2  
Food| sold out  
  
## 5\. codes with leading zeros

Code| Postcode| Label  
---|---|---  
007| 01234| agent  
042| 00501| answer  
  
## 6\. dates

Shipped| Delivered| Parcels  
---|---|---  
2026-09-01| 2026-09-03| 3  
2026-09-10| 2026-09-15| 1  
  
## 7\. links

[Product](/docs/product)| Docs  
---|---  
Ant Farm Deluxe| [manual](https://example.com/deluxe)  
Magnifier| none  
  
## 8\. hidden row

Sku| Stock  
---|---  
AF-1| 5  
AF-2| 0  
AF-3| 12  
  
## 9\. nested

Warehouse| Bins  
---|---  
Berlin|  | Bin| Count  
---|---  
B1| 40  
B2| 15  
Lyon| none  
  
## 10\. no thead, td header row

Metric| Value  
---|---  
Uptime| 99.9  
Errors| 3  
  
## 11\. european numbers

Country| Revenue| Growth  
---|---|---  
Germany| 1.234.567,89| 3,5  
France| 987.654,32| -1,2  
Spain| n/a| 0,0

