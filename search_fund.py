import boto3
from boto3.dynamodb.conditions import Attr

import sys

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

table = dynamodb.Table("fund_details")

contains_string = sys.argv[1]

fe = Attr("fund_short_name").contains(contains_string)
#pe = "fund_id,fund_short_name,fund_long_name"

#response = table.scan(FilterExpression=fe, ProjectionExpression=pe)
response = table.scan(FilterExpression=fe)


if response['Count'] > 0:
    print(response['Items'][0])
else:
    print("No items found")
