# exit on any failures
set -e

# this is to delete the 'students' table and ignore any errors in case it doesn't exist
curl --fail -v -X DELETE api/tables/manage/students || echo "ignoring error on delete in case it didn't exist already"

# create a 'students' table with fields 'id', 'first_name', 'last_name', 'grade' and with 'id' as the primary key
curl --fail -v -X POST -d '{"key": "last_name", "fields": {"last_name": "string", "first_name": "string", "grade": "int"}}' api/tables/manage/students

# make 3 entries into the 'students' table
curl --fail -v -X POST -d '[{"last_name": "Hoffman", "first_name": "Dustin", "grade": 8}]' api/tables/students
curl --fail -v -X POST -d '[{"last_name": "Sanchez", "first_name": "Rick", "grade": 9}, {"last_name": "Smith", "first_name": "Morty", "grade": 10}]' api/tables/students

# read only one row
expected_count=1
actual_count=$(curl --fail "api/tables/students?last_name='Sanchez'" | jq length)
[ "$actual_count" == "$expected_count" ] || { echo "expected $expected_count records, found $actual_count" && exit 1; }

# delete 1 entry from the 'students' table
curl --fail -v -X DELETE "api/tables/students?field=last_name&value='Hoffman'"

# make sure there are 2 entries in the 'students' table
expected_count=2
actual_count=$(curl --fail api/tables/students | jq length)
[ "$expected_count" == "$actual_count" ] || { echo "expected $expected_count records, found $actual_count" && exit 1; }

# delete the 'students' table
curl --fail -v -X DELETE api/tables/manage/students

# test no_op
[ "$(curl --fail api/tables/students?no_op=true)" == "SELECT * FROM students" ] || { echo "did not return expected SQL command for no_op" && exit 1; }


