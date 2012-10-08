import glob
import datetime
import os
import uuid

from pyramid.view import view_config


MODEL_ID_KEY = 'model_id'
MISSING_MODEL_ERROR = 'The model you were working on was deleted. Please ' \
                      'reload it from a save file or start again.'


# A dictionary containing the active `py_gnome.model.Model` instances.
_running_models = {}


class MockModel(object):
    """
    A mock stand-in for what will eventually be a `py_gnome.model.Model`.
    """
    def __init__(self):
        self.id = uuid.uuid4()

    def get_movers(self):
        return []

    def get_settings(self):
        return [
            {'name': 'ID', 'value': self.id}
        ]

    def get_map(self):
        return {'name': 'My map'}

    def get_spills(self):
        return []

    def run(self):
        frames_glob = os.path.join(
            os.path.dirname(__file__), 'static', 'img', 'test_frames', '*.jpg')
        images = glob.glob(frames_glob)

        # Mock out some timestamps until we accept this input from the user.
        two_weeks_ago = datetime.datetime.now() - datetime.timedelta(weeks=4)

        timestamps = [two_weeks_ago + datetime.timedelta(days=day_num)
                      for day_num in range(len(images))]

        return [
            dict(url=image.split('webgnome')[-1], timestamp=timestamps[i])
            for i, image in enumerate(images)]


@view_config(route_name='show_model', renderer='model.mak')
def show_model(request):
    """
    Show the current user's model.

    Get or create an existing `py_gnome.model.Model` using the `model_id`
    field in the user's session.

    If `model_id` was found in the user's session but the model did not exist,
    warn the user and suggest that they reload from a save file.
    """
    model_id = request.session.get(MODEL_ID_KEY, None)
    model = None

    if model_id:
        model = _running_models.get(model_id, None)
        if model is None:
            request.session.flash(MISSING_MODEL_ERROR)

    if model is None:
        model = MockModel()
        _running_models[model.id] = model
        request.session[MODEL_ID_KEY] = model.id

    return {'model': model}


@view_config(route_name='run_model', renderer='gnome_json')
def run_model(request):
    model_id = request.session.get(MODEL_ID_KEY, None)
    data = {}

    if model_id is None:
        data['error'] = True
        data['message'] = 'Model not found.'
        return data

    model = _running_models.get(model_id, None)

    if model is None:
        data['error'] = True
        data['message'] = MISSING_MODEL_ERROR
        return data

    data['result'] = model.run()

    return data
