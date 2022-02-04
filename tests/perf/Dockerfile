FROM ubuntu

# install libs
RUN apt-get update -y && apt-get install -y curl jq

# copy test script
COPY run.sh /

# set command to run test script
CMD bash /run.sh
