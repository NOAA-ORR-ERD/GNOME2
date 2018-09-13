'''
tests for kmz outputter
'''

import os
from datetime import datetime, timedelta

import pytest
from pytest import raises

from gnome.outputters import ShapeOutput

from gnome.spill import point_line_release_spill
from gnome.spill_container import SpillContainerPair


def local_dirname():
    dirname = os.path.split(__file__)[0]
    dirname = os.path.join(dirname, "output_shape")
    if not os.path.exists(dirname):
        os.mkdir(dirname)
    return dirname

@pytest.fixture(scope='function')
def output_filename(output_dir, request):
    '''
    trying to create a unique file for tests so pytest_xdist doesn't have
    issues.
    '''
    dirname = output_dir
    if not os.path.exists(dirname):
        os.mkdir(dirname)

    file_name = request.function.func_name
    if request._pyfuncitem._genid is None:
        file_name += '_sample'
    else:
        file_name += '_' + request._pyfuncitem._genid + '_sample'

    return os.path.join(dirname, file_name)


@pytest.fixture(scope='function')
def model(sample_model, output_filename):
    model = sample_model['model']
    rel_start_pos = sample_model['release_start_pos']
    rel_end_pos = sample_model['release_end_pos']

    model.cache_enabled = True
    model.uncertain = True

    model.spills += point_line_release_spill(2,
                                             start_position=rel_start_pos,
                                             release_time=model.start_time,
                                             end_position=rel_end_pos)

    model.time_step = 3600
    model.duration = timedelta(hours=1)
    model.rewind()

    return model


def test_init(output_dir):
    'simple initialization passes'
    shp = ShapeOutput(os.path.join(output_dir, 'test'))


def test_init_exceptions():
    '''
    test exceptions raised during __init__
    '''
    with pytest.raises(ValueError):
        # must be filename, not dir name
        ShapeOutput(os.path.abspath(os.path.dirname(__file__)))

    with pytest.raises(ValueError):
        ShapeOutput('invalid_path_to_file/file.kmz')


def test_exceptions(output_filename):
    spill_pair = SpillContainerPair()

    # begin tests
    shp = ShapeOutput(output_filename)
    shp.rewind()  # delete temporary files

    with raises(TypeError):
        # need to pass in model start time
        shp.prepare_for_model_run(num_time_steps=4)

    with raises(TypeError):
        # need to pass in model start time and spills
        shp.prepare_for_model_run()

    with raises(ValueError):
        # need a cache object
        shp.write_output(0)

#    Maybe add ability to specify which data later on..
#    with raises(ValueError):
#        kmz.which_data = 'some random string'

    # changed renderer and netcdf ouputter to delete old files in
    # prepare_for_model_run() rather than rewind()
    # -- rewind() was getting called a lot
    # -- before there was time to change the output file names, etc.
    # So for this unit test, there should be no exception if we do it twice.
    shp.prepare_for_model_run(model_start_time=datetime.now(),
                                 spills=spill_pair,
                                 num_time_steps=4)
    shp.prepare_for_model_run(model_start_time=datetime.now(),
                                 spills=spill_pair,
                                 num_time_steps=4)


    # with raises(AttributeError):
    #     'cannot change after prepare_for_model_run has been called'
    #     kmz.which_data = 'most'

def test_timesteps(model):
    filename = os.path.join(local_dirname(), "multi_timesteps")

    shp = ShapeOutput(filename)
    model.outputters += shp

    #run the model
    model.full_run()





