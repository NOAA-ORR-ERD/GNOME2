#Updates a save loaded using pygnome.Model to the latest version

from __future__ import print_function

import json
import logging
import glob
import sys
import contextlib
import os
import six
import re
import zipfile

log = logging.getLogger(__name__)

errortypes = [
    'Save file version not compatible with this updater. Version: {0} Updater: {1}',
    'Save file does not have a version.txt',
    'Failed to remove old file: {0} Error: {1}',
]


@contextlib.contextmanager
def remember_cwd(new_wd):
    curdir= os.getcwd()
    os.chdir(new_wd)
    try: yield
    finally: os.chdir(curdir)


def update_savefile(save_directory):
    if not isinstance(save_directory, six.string_types) or not os.path.isdir(save_directory):
        raise ValueError('Must unzip save to directory in order to upgrade it to latest version')
    
    messages = []
    errors = []

    with remember_cwd(save_directory):
        #get current save file version
        allfiles = glob.glob('*')
        if 'version.txt' in allfiles:
            with open('version.txt') as fp:
                v = int(fp.readline())
        else:
            v = 0

        for i in range(v, len(all_update_steps)):
            #execute update
            step = all_update_steps[i]
            messages, errors = step(messages, errors)

            if len(errors) > 0:
                for e in errors:
                    sys.stderr.write(e+'\n')
                raise ValueError('Errors occurred during save update process')

        if len(messages) > 0:
            for m in messages:
                log.info(m)
        return True


def v0tov1(messages, errors):
    '''
    Takes a zipfile containing no version.txt and up-converts it to 'version 1'.
    This functions purpose is to upgrade save files to maintain compatibility
    after the SpillRefactor upgrades.
    '''
    def Substance_from_ElementType(et_json, water):
        '''
        Takes element type cstruct with a substance, creates an appropriate GnomeOil cstruct
        '''
        if 'substance' not in et_json:
            '''
            Note the id of the new cstructs. The ID IS required at this stage, because
            the load process will use it later to establish references between objects
            '''
            substance = {
                "obj_type": "gnome.spill.substance.NonWeatheringSubstance", 
                "name": "NonWeatheringSubstance", 
                "standard_density": 1000.0, 
                "initializers": et_json.get('initializers',[]),
                "is_weatherable": False, 
                "id": "v0-v1-update-id-0"
            }
        else:
            substance = {
                "obj_type": "gnome.spill.substance.GnomeOil", 
                "name": et_json.get('substance', 'Unknown Oil'),  
                "initializers": et_json.get('initializers', []),
                "is_weatherable": True,
                "water": water,
                "id": "v0-v1-update-id-1"
            }
            if isinstance(et_json.get('substance', None), dict):
                substance.update(et_json.get('substance'))

        return substance

    jsonfiles = glob.glob('*.json')

    log.debug('updating save file from v0 to v1 (Spill Refactor)')
    water_json = element_type_json = None
    spills = []
    inits = []
    for fname in jsonfiles:
        with open(fname, 'r') as fn:
            json_ = json.load(fn)
            if 'obj_type' in json_:
                if 'Water' in json_['obj_type'] and 'environment' in json_['obj_type'] and water_json is None:
                    water_json = (fname, json_)
                if 'element_type.ElementType' in json_['obj_type'] and element_type_json is None:
                    element_type_json = (fname, json_)
                if 'gnome.spill.spill.Spill' in json_['obj_type']:
                    spills.append((fname, json_))
                if 'initializers' in json_['obj_type']:
                    inits.append((fname, json_))

    # Generate new substance object
    if water_json is None:
        water_json = (None, None)

    substance=None
    if element_type_json is not None:
        substance = Substance_from_ElementType(element_type_json[1], water_json[1])
        substance_fn = sanitize_filename(substance['name'] + '.json')

    # Delete .json for deprecated objects (element_type)
    fn = element_type_json[0]
    try:
        os.remove(fn)
    except Exception as e:
        err = errortypes[2].format(fn, e)
        errors.append(err)
        return messages, errors

    # Write modified and new files
    if substance is not None:
        with open(substance_fn, 'w') as subs_file:
            json.dump(substance, subs_file, indent=True)
    for spill in spills:
        fn, sp = spill
        del sp['element_type']
        sp['substance'] = substance_fn
        with open(fn, 'w') as fp:
            json.dump(sp, fp, indent=True)
    for init in inits:
        fn, init = init
        init['obj_type'] = init['obj_type'].replace('.elements.', '.')
        with open(fn, 'w') as fp:
            json.dump(init, fp, indent=True)
    with open('version.txt', 'w') as vers_file:
        vers_file.write('1')

    messages.append('**Update from v0 to v1 successful**')
    return messages, errors


def extract_zipfile(zip_file, to_folder='.'):
    with zipfile.ZipFile(zip_file, 'r') as zf:
        folders = [name for name in zf.namelist() if name.endswith('/') and not name.startswith('__MACOSX')]
        prefix=None
        if len(folders) == 1:
            # we allow our model content to be in a single top-level folder
            prefix = folders[0]

        fn_edits = {}
        for name in zf.namelist():
            if (prefix and name.find(prefix) != 0) or name.endswith('/'):
                #ignores the __MACOSX files
                pass
            else:
                orig = os.path.basename(name)
                fn = sanitize_filename(orig)
                if orig != fn:
                    log.info('Invalid filename found: {0}'.format(orig))
                    fn_edits[orig] = fn
                    
                target = os.path.join(to_folder, fn)
                with open(target, 'wb') as f:
                    f.write(zf.read(name))
        if len(fn_edits) > 0 :
            log.info('Save file contained invalid names. Editing extracted json to maintain save file integrity.')
            for jsonfile in glob.glob(os.path.join(to_folder,'*.json')):
                #if any file name edits were made, references may need to be updated too
                #otherwise the .json file wont be found
                contents = None
                replaced = False
                with open(jsonfile, 'r') as jf:
                    contents = jf.read()
                    for k, v in fn_edits.items():
                        if k in contents:
                            contents = contents.replace(k, v)
                            replaced = True
                if replaced:
                    with open(jsonfile, 'w') as jf:
                        jf.write(contents)


def sanitize_filename(fname):
    '''
    '''
    if sys.platform == "win32":
        return re.sub(r'[\\\\/*?:"<>|]', "", fname)
    else:
        return re.sub(r'[/]', "", fname)

all_update_steps = [v0tov1,]