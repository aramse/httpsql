# fail on any errors
set -e

ORDINAL=$(hostname | rev | cut -d '-' -f 1 | rev)

# set a name that's unique to the test container instance
TABLE=students_$ORDINAL

# delete the 'students' table if exists
curl --fail -v -X DELETE api/tables/manage/$TABLE || echo "not failing, since it may not exist"

# define a 'students' table
curl --fail -v -X POST -d '{"key": "id", "fields": {"id": "int", "first_name": "string", "last_name": "string", "grade": "int"}}' api/tables/manage/$TABLE

COUNT=1000

# run $COUNT calls, each of which inserts 2 students, failing if any don't succeed
for i in $(seq 1 $COUNT); do
  curl --fail -sss -X POST -d "[{\"id\": $i, \"first_name\": \"Rick\", \"last_name\": \"Sanchez\", \"grade\": 10}, {\"id\": $(($i + $COUNT)), \"first_name\": \"Morty\", \"last_name\": \"Smith\", \"grade\": 9}]" api/tables/$TABLE || { echo "failed on insert #$i" && RET=1 && break; }
done

# make sure there are 2000 students (2*1000)
expected_count=2000
actual_count=$(curl -v api/tables/$TABLE | jq length)
[ "$expected_count" == "$actual_count" ] || { echo "expected $expected_count records, found $actual_count" && exit 1; }

exit $RET
