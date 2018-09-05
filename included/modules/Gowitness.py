#!/usr/bin/python

from database.repositories import IPRepository, DomainRepository, PortRepository, UrlRepository
from included.ModuleTemplate import ToolTemplate
from subprocess import Popen
from included.utilities import which, get_urls
import shlex
import os
import pdb
import tempfile
from time import time
import glob

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


class Module(ToolTemplate):
    
    name = "Gowitness"
    binary_name = "gowitness"

    def __init__(self, db):
        self.db = db
        self.IPAddress = IPRepository(db, self.name)
        
    def set_options(self):
        super(Module, self).set_options()

        self.options.add_argument('-i', '--import_database', help="Import URLs from the database", action="store_true")
        self.options.add_argument('-f', '--import_file', help="Import URLs from file")
        self.options.add_argument('--group_size', help="How many hosts per group (default 250)", type=int, default=250)
        self.options.add_argument('--rescan', help="Rerun gowitness on systems that have already been processed.", action="store_true")
        self.options.add_argument('--scan_folder', help="Generate list of URLs based off of a folder containing GobusterDir output files")
        self.options.add_argument('--counter_max', help="Max number of screenshots per host", default="20")

    def get_targets(self, args):
    
        timestamp = str(int(time()))
        targets = []
        if args.import_file:
            targets += [t for t in open(args.file).read().split('\n') if t]
            
        if args.import_database:
            if args.rescan:
                targets += get_urls.run(self.db, scope_type="active")
            else:
                targets += get_urls.run(self.db, scope_type="active", tool=self.name)

        if args.scan_folder:

            files = os.listdir(args.scan_folder)
            counter_max = str(args.counter_max)
            for f in files:
                    
                if f.count('_') == 4:
                    counter = 0    
                    http, _, _, domain, port = f.split('-dir.txt')[0].split('_')
                    for data in open(os.path.join(args.scan_folder, f)).read().split('\n'):
                        if '(Status: 200)' in data:
                            targets.append("{}://{}:{}{}".format(http, domain, port, data.split(' ')[0]))
                            counter += 1
                        if counter >= counter_max:
                            break

        if args.output_path[0] == "/":
            self.path = os.path.join(self.base_config['PROJECT']['base_path'], args.output_path[1:], timestamp, args.output_path[1:] +"_{}" )
        else:
            self.path = os.path.join(self.base_config['PROJECT']['base_path'], args.output_path, timestamp, args.output_path+"_{}" )


        res = []
        i = 0

        for url_chunk in self.chunks(targets, args.group_size):
            i += 1

            _, file_name = tempfile.mkstemp()
            open(file_name, 'w').write('\n'.join(url_chunk))
            if not os.path.exists(self.path.format(i)):
                os.makedirs(self.path.format(i))
            res.append({'target':file_name, 'output':self.path.format(i)})

        return res

    def build_cmd(self, args):

        command = self.binary + " file -D {output}/gowitness.db -d {output} -s {target} "

        if args.tool_args:
            command += tool_args

        return command
            
    def process_output(self, cmds):
        '''
        Not really any output to process with this module, but you need to cwd into directory to make database generation work, so
        I'll do that here.
        '''    
            
        cwd = os.getcwd()
        for cmd in cmds:
            target = cmd['target']
            output = cmd['output']

            cmd = [self.binary, "generate"]
            os.chdir(output)

            Popen(cmd, shell=False).wait()

        os.chdir(cwd)
        self.IPAddress.commit()

    def chunks(self, chunkable, n):
        """ Yield successive n-sized chunks from l.
        """
        for i in xrange(0, len(chunkable), n):
            yield chunkable[i:i+n]