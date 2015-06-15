from redfish import connection

host = '127.0.0.1'
user_name = 'Admin'
password = 'password'
server = connection.RedfishConnection(host, user_name, password)