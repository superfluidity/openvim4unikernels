import yaml


def get_config(file):
    """
    Parse test config file
    :param file: 
    :return: 
    """
    with open(file, 'r') as stream:
        try:
            return yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)

