import os
from pathlib import Path
from fabric.api import *
from fabric.contrib.files import exists
from glob import glob


env.hosts = open('InstancesConfigurations/public_ips', 'r').read().splitlines()
# Set this to the username on the machines running the benchmark (possibly 'ubuntu')
env.user = 'ubuntu'
# env.password=''
# Set this to point to where the AWS key is put by MATRIX (possibly ~/Keys/[KEYNAME])
env.key_filename = [f'{Path.home()}/Keys/AWSKeys/Matrixuseast1.pem']
# Set this to point to where you put the MATRIX root
path_to_matrix = 'YOU PATH TO MATRIX'


@task
def install_git_project(git_address, git_branch, working_directory):
    """
    Install the protocol at the working directory with the GitHub credentials
    :type git_address str
    :param git_address: GitHub project address
    :type git_branch str
    :param git_branch: GitHub project branch
    :type working_directory str
    :param working_directory: directory to clone the GitHub repository to
    """
    if not exists(working_directory):
        run(f'git clone {git_address} {working_directory}')

    with cd(working_directory):
        run('git pull')
        run(f'git checkout {git_branch}')
        run('./MATRIX/build.sh')


@task
def update_libscapi():
    """
    Update libscapi library on the remote servers from dev branch
    """
    with cd('libscapi/'):
        run('git checkout dev')
        run('git pull')
        run('make')


def prepare_for_execution(number_of_regions, args, executable_name, working_directory):
    """
    Prepare the arguments for execution for all execution modes('normal', profiler and latency)
    :param number_of_regions:
    :param args:
    :param executable_name:
    :param working_directory:
    :return: string of values for execution and party id for each host
    """
    values = args.split('@')
    values_str = ''
    party_id = env.hosts.index(env.host)

    for val in values:
        # for external protocols
        if val == 'partyid':
            values_str += f'{str(env.hosts.index(env.host) - 1)} '
        else:
            values_str += f'{val} '

    with warn_only():
        sudo("kill -9 `ps aux | grep %s | awk '{print $2}'`" % executable_name)

    if 'inputs0' in values_str:
        values_str = values_str.replace('input_0.txt', f'input_{str(party_id)}.txt')

    if int(number_of_regions) > 1:
        put(f'InstancesConfigurations/parties{party_id}.conf', working_directory)
        run(f'mv {working_directory}/parties{party_id}.conf {working_directory}/parties.conf')
    else:
        put('InstancesConfigurations/parties.conf', working_directory)

    return values_str, party_id


@task
def run_protocol(number_of_regions, args, executable_name, working_directory,
                 coordinator_executable=None, coordinator_config=None):
    """
    Execute the protocol on remote servers
    :type number_of_regions int
    :param number_of_regions: number of regions
    :type args str
    :param args: the arguments for the protocol, separated by `@`
    :type executable_name str
    :param executable_name: the executable file name
    :type working_directory str
    :param working_directory: the executable file dir
    :type coordinator_executable str
    :param coordinator_executable: coordinator executable name
    :type coordinator_config str
    :param coordinator_config: coordinator args
    """

    values_for_execution, party_id = prepare_for_execution(number_of_regions, args, executable_name, working_directory)

    # local execution
    if number_of_regions == 0:
        number_of_parties = len(env.hosts)
        local(f'cp InstancesConfigurations/parties.conf {working_directory}/MATRIX')
        for idx in range(number_of_parties):
            local(f'cd {working_directory}/MATRIX && ./{executable_name} {idx} {values_for_execution} &')

    # remote execution (servers or cloud)
    else:
        with cd(working_directory):
            # public ips are required for SCALE-MAMBA
            put('InstancesConfigurations/public_ips', working_directory)
            # required for SCALE-MAMBA to rsync between AWS instances
            with warn_only():
                put(env.key_filename[0], run('pwd'))

            with warn_only():
                sudo("kill -9 `ps aux | grep %s | awk '{print $2}'`" % executable_name)

            # run protocols with coordinator
            if coordinator_executable is not None:
                if env.hosts.index(env.host) == 0:
                    coordinator_args = coordinator_config['coordinatorConfig'].split('@')
                    coordinator_values_str = ''

                    for coordinator_val in coordinator_args:
                        coordinator_values_str += f'{coordinator_val} '

                    run(f'{coordinator_executable} {coordinator_values_str}')
                    try:
                        with open('Execution/execution_log.log', 'a+') as log_file:
                            log_file.write(f'{values_for_execution}\n')
                    except EnvironmentError:
                        print('Cannot write data to execution log file')
                else:
                    run(f'./{executable_name} {party_id - 1} {values_for_execution}')
                    try:
                        with open('Execution/execution_log.log', 'a+') as log_file:
                            log_file.write(f'{values_for_execution}\n')
                    except EnvironmentError:
                        print('Cannot write data to execution log file')

            # run protocols with no coordinator
            else:
                run('mkdir -p logs')
                run(f'./MATRIX/run.sh {party_id} {values_for_execution}')
                try:
                    with open('Execution/execution_log.log', 'a+') as log_file:
                        log_file.write(f'{values_for_execution}\n')
                except EnvironmentError:
                    print('Cannot write data to execution log file')


@task
def run_protocol_profiler(number_of_regions, args, executable_name, working_directory):
    """
    Execute the protocol on remote servers with profiler.
    The first party is executed with profiler, the other executed normally
    :type number_of_regions int
    :param number_of_regions: number of regions
    :type args str
    :param args: the arguments for the protocol, separated by `@`
    :type executable_name str
    :param executable_name: the executable file name
    :type working_directory str
    :param working_directory: the executable file dir
    """

    values_for_execution, party_id = prepare_for_execution(number_of_regions, args, executable_name, working_directory)

    if party_id == 0:
        run(f'valgrind --tool=callgrind ./{executable_name} partyID {party_id} {values_for_execution}')
        get('callgrind.out.*', os.getcwd())

    else:
        run(f'./{executable_name} partyID {party_id} {values_for_execution}')
        try:
            with open('Execution/execution_log.log', 'a+') as log_file:
                log_file.write(f'{values_for_execution}\n')
        except EnvironmentError:
            print('Cannot write data to execution log file')


@task
def run_protocol_memory_profiler(number_of_regions, args, executable_name, working_directory):
    """
    Execute the protocol on remote servers with profiler.
    The first party is executed with profiler, the other executed normally
    :type number_of_regions int
    :param number_of_regions: number of regions
    :type args str
    :param args: the arguments for the protocol, separated by `@`
    :type executable_name str
    :param executable_name: the executable file name
    :type working_directory str
    :param working_directory: the executable file dir
    """

    values_for_execution, party_id = prepare_for_execution(number_of_regions, args, executable_name, working_directory)

    if party_id == 0:
        run(f'valgrind --tool=massif ./{executable_name} partyID {party_id} {values_for_execution}')
        get('massif.out.*', os.getcwd())

    else:
        run(f'./{executable_name} partyID {party_id} {values_for_execution}')
        try:
            with open('Execution/execution_log.log', 'a+') as log_file:
                log_file.write(f'{values_for_execution}\n')
        except EnvironmentError:
            print('Cannot write data to execution log file')


@task
def run_protocol_with_latency(number_of_regions, args, executable_name, working_directory):
    """
    Execute the protocol on remote servers with network latency
    :type number_of_regions int
    :param number_of_regions: number of regions
    :type args str
    :param args: the arguments for the protocol, separated by `@`
    :type executable_name str
    :param executable_name: the executable file name
    :type working_directory str
    :param working_directory: the executable file dir
    """

    values_for_execution, party_id = prepare_for_execution(number_of_regions, args, executable_name, working_directory)
    with cd(working_directory):
        # the warning required for multi executions.
        # If you delete this line it will failed if you don't reboot the servers
        with warn_only():
            sudo('tc qdisc add dev ens5 root netem delay 300ms')

        run(f'./{executable_name} partyID {party_id} {values_for_execution}')
        try:
            with open('Execution/execution_log.log', 'a+') as log_file:
                log_file.write(f'{values_for_execution}\n')
        except EnvironmentError:
            print('Cannot write data to execution log file')


@task
def collect_results(results_server_directory, results_local_directory):
    """
    :type results_server_directory str
    :param results_server_directory: the remote directory of the JSON results files
    :type results_local_directory str
    :param results_local_directory: the directory that the results are copied
    """
    local(f'mkdir -p {results_local_directory}')
    get(f'{results_server_directory}/*.json', results_local_directory)


@task
def get_logs(protocol_name, working_directory):
    """
    Collect logs from the specified working directory
    :type protocol_name str
    :param protocol_name: protocol name that logs should be received
    :type working_directory str
    :param working_directory: working directory for the protocol
    """
    logs_directory = f'{protocol_name}_Logs/'
    local(f'mkdir -p {logs_directory}')
    get(f'{working_directory}/*.log', f'{logs_directory}')


@task
def delete_old_experiment(working_directory):
    run(f'rm {working_directory}/*.json')
    run(f'rm {working_directory}/*.log')


@task
def copy_circuits_from_db(working_directory):
    # add the circuits db to known hosts. Private IP is used to reduce costs.
    # copy the key for scp command
    files = glob(f'{os.getcwd()}/newCircuits/*')
    for file in files:
        put(file, f'{working_directory}/assets/')






