const fs = require('fs');
const redis = require('redis');
const ssh = require('node-ssh');

/*
* State has 4 values:
* 1. OPEN
* 2. CLOSED
* 3. RUN
* 4. COMPLETED
*/

exports.openForRegistration = function (req, res)
{
    let client = redis.createClient();
    client.del('addresses', function (err) {
        console.log(err);
    });
    res.redirect('/polls');
};

exports.registerToPoll = function (req, res) {
    let pollName = req.params.pollName;
    let clientIp = req.params.ip;
    let type = req.params.type;

    let client = redis.createClient();

    // insert ip address to addresses table
    client.rpush('addresses', clientIp, function (err) {
        if (err) console.log("Error in address registration");
    });

    client.rpush(pollName, clientIp.toString(), type.toString(),
        function (err) {
        if(err) console.log("Error in registration");
    });
    res.redirect('/polls');
};

exports.getPollsParams = function (req, res) {
    let pollName = req.params.pollName;
    let ip = req.params.ip;
    let jsonData = {};
    let client = redis.createClient();
    client.lrange('execution' + pollName, 0, -1, function (err, data) {
        if(err) console.log(err);
        console.log(data.length);
        for (let idx = 0; idx < data.length; idx+=20)
        {
            if(data[idx] === ip)
            {
                for(let idx2 = idx + 2; idx2 < 19; idx2+=2)
                    jsonData[data[idx2]] = data[idx2 + 1];
                break
            }
        }
        jsonData['circuitFileAddress'] =  'http://35.171.69.162/polls/circuit/';

        res.json(jsonData);
    });


};

exports.changePollState = function (req, res) {

};

exports.closePollForRegistration = function (req, res) {
    req.session.state = "CLOSED";
    let pollName = req.params.pollName ;
    let client = redis.createClient();

    let numberOfParties = 0;
    let registeredIps = []; // save addresses for the json files
    let ips = [];
    let idx = 0;
    client.lrange(pollName, 0, -1, function (err, data) {
        if (err) console.log('Error retrieve poll data');
        for (idx = 0; idx < data.length; idx += 2)
        {
            registeredIps.push(data[idx]);
            let port = 9000 + numberOfParties;
            ips.push('34.239.19.87' + ':' + port.toString());
            numberOfParties++;
        }
    });

    client.lrange('addresses', numberOfParties, -1, function (err, data) {
        if (err) console.log('Error retrieve addresses');

        //write addresses to file
        let fileName = __dirname + '/../public/assets/parties.conf';
        //delete file if exists
        fs.unlink(fileName, function (err) {console.log(err)});

        for(let idx = 0; idx < ips.length; idx++)
        {
            fs.appendFileSync(fileName, ips[idx] + '\n');
        }

        let partiesSize = ips.length;

        let exec = require('child_process').exec;
        let createCircuit = 'java -jar ' + __dirname + '/../public/assets/GenerateArythmeticCircuitForVariance.jar '
            + partiesSize.toString() + ' 1';
        exec(createCircuit, function (error, stdout){
            if(error) console.log('Error: ' + error);
            console.log(stdout);
        });

        //copy the circuit to the public path
    let circuitName = 'ArythmeticVarianceFor1InputsAnd' + partiesSize + 'Parties.txt';

    // extract cli parameters for online users
    for(let ipsIdx = 0; ipsIdx < ips.length; ipsIdx++)
    {
        let jsonData = {};
        jsonData['partyID'] = ipsIdx.toString();
        jsonData['partiesNumber'] = partiesSize.toString();
        jsonData['inputFile'] = 'inputSalary' + ipsIdx + '.txt';
        jsonData['outputFile'] = 'output.txt';
        jsonData['circuitFile'] = 'http://35.171.69.162/polls/circuit/' + circuitName;
        jsonData['proxyAddress'] = '34.239.19.87';
        jsonData['partiesFile'] = 'http://35.171.69.162/polls/parties/';
        jsonData['fieldType'] = 'ZpMersenne';
        jsonData['internalIterationsNumber'] = '1';
        jsonData['NG'] = '1';
        let dataFileName =  __dirname + '/../public/assets/' + registeredIps[ipsIdx].split(':')[0]+'.json';
        fs.writeFile(dataFileName, JSON.stringify(jsonData), 'utf8', function (err) {
            if (err) console.log(err);
        });
    }
        let copyCommand = 'cp ' + __dirname + '/../' +  circuitName + ' ' + __dirname + '/../public/assets/';
        exec(copyCommand, function (error) {
            if(error) console.log('Error: ' + error);
        });
    });

    //launch proxies
    // runProxyClients(req, res);

    res.redirect('/polls')
};

exports.runProxyClients = function(req, res)
{
    let filePath = __dirname + '/../public/assets/parties.conf';
    fs.readFile(filePath, {encoding: 'utf-8'}, function(err, data){
        let splitedData = data.split("\n");
        let newData = [];
        for(let idx = 0; idx < splitedData.length; idx++)
        {
            let ip = splitedData[idx].split(":")[0];
            let port = splitedData[idx].split(":")[1];
            if (ip === "34.239.19.87")
            {
                let newIp = "127.0.0.1";
                newData.push(newIp + ":" + port + "\n");
            }
            else newData.push(splitedData[idx] + "\n");
        }

        let proxyFileNames = __dirname + '/../public/assets/partiesProxy.conf';
        fs.writeFile(proxyFileNames, newData.join(""), function (err) {
            if(err) console.log(err);
        });
    });

    // ssh to copy to proxy server

    let sshClient = new ssh();
        sshClient.connect({host: 'localhost', username: 'ubuntu',
            privateKey: '~/Keys/matrix.pem'});

    res.redirect('/polls');
};