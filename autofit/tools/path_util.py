import os


def make_and_return_path_from_path_and_folder_names(path, folder_names):
    """ For a given path, create a directory structure composed of a set of folders and return the path to the \
    inner-most folder.

    For example, if path='/path/to/folders', and folder_names=['folder1', 'folder2'], the directory created will be
    '/path/to/folders/folder1/folder2/' and the returned path will be '/path/to/folders/folder1/folder2/'.

    If the folders already exist, routine continues as normal.

    Parameters
    ----------
    path : str
        The path where the directories are created.
    folder_names : [str]
        The names of the folders which are created in the path directory.

    Returns
    -------
    path
        A string specifying the path to the inner-most folder created.

    Examples
    --------
    path = '/path/to/folders'
    path = make_and_return_path(path=path, folder_names=['folder1', 'folder2'].
    """
    for folder_name in folder_names:

        path += folder_name + '/'

        try:
            os.makedirs(path)
        except FileExistsError:
            pass

    return path
