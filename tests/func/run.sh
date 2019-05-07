# exit on any failures
set -e

# this is to delete the 'students' table and ignore any errors in case it doesn't exist
curl --fail -v -X DELETE api/tables/manage/students || echo "ignoring error on delete in case it didn't exist already"

# define a 'students' table with fields 'id', 'first_name', 'last_name', 'grade' and with 'id' as the primary key
curl --fail -v -X POST -d '{"key": "id", "fields": {"id": "int", "first_name": "string", "last_name": "string", "grade": "int"}}' api/tables/manage/students

# make 2 entries into the 'students' table
curl --fail -v -X POST -d '[{"id": 1, "first_name": "Rick", "last_name": "Sanchez", "grade": 10}, {"id": 2, "first_name": "Morty", "last_name": "Smith", "grade": 9}]' api/tables/students

# read only one row
expected_count=1
actual_count=$(curl --fail "api/tables/students?first_name='Rick'&last_name='Sanchez'" | jq length)
[ "$actual_count" == "$expected_count" ] || { echo "expected $expected_count records, found $actual_count" && exit 1; }

# delete 1 entry from the 'students' table
curl --fail -v -X DELETE 'api/tables/students?fName=id&fValue=2'

# make sure there is 1 entry in the 'students' table
expected_count=1
actual_count=$(curl --fail api/tables/students | jq length)
[ "$expected_count" == "$actual_count" ] || { echo "expected $expected_count records, found $actual_count" && exit 1; }

# delete the 'students' table
curl --fail -v -X DELETE api/tables/manage/students

# test no_op
[ "$(curl --fail api/tables/students?no_op=true)" == "SELECT * FROM students" ] || { echo "did not return expected SQL command for no_op" && exit 1; }


