# -*- coding: utf-8 -*-
'''
    vdirsyncer.sync
    ~~~~~~~~~~~~~~~

    The function in `vdirsyncer.sync` can be called on two instances of
    `Storage` to syncronize them. Due to the abstract API storage classes are
    implementing, the two given instances don't have to be of the same exact
    type. This allows us not only to syncronize a local vdir with a CalDAV
    server, but also syncronize two CalDAV servers or two local vdirs.

    :copyright: (c) 2014 Markus Unterwaditzer
    :license: MIT, see LICENSE for more details.
'''

def sync(storage_a, storage_b, status):
    '''Syncronizes two storages.

    :param storage_a: The first storage
    :type storage_a: :class:`vdirsyncer.storage.base.Storage`
    :param storage_b: The second storage
    :type storage_b: :class:`vdirsyncer.storage.base.Storage`
    :param status:
        {uid: (etag_a, etag_b)}, metadata about the two storages for detection
        of changes. Will be modified by the function and should be passed to it
        at the next sync. If this is the first sync, an empty dictionary should
        be provided.
    '''
    list_a = dict(storage_a.list())  # {uid: etag}
    list_b = dict(storage_b.list())

    items_a = {}  # items prefetched for copy
    items_b = {}  # {uid: (item, etag)}

    actions, prefetch_from_a, prefetch_from_b = \
        get_actions(list_a, list_b, status)

    def prefetch():
        for item, uid, etag in storage_a.get_multi(prefetch_from_a):
            items_a[uid] = (item, etag)
        for item, uid, etag in storage_b.get_multi(prefetch_from_b):
            items_b[uid] = (item, etag)
    prefetch()

    storages = {
        'a': (storage_a, items_a, list_a),
        'b': (storage_b, items_b, list_b),
        None: (None, None, None)
    }

    for action, uid, source, dest in actions:
        source_storage, source_items, source_list = storages[source]
        dest_storage, dest_items, dest_list = storages[dest]

        if action in ('upload', 'update'):
            item, source_etag = source_items[uid]
            if action == 'upload':
                dest_etag = dest_storage.upload(item)
            else:
                dest_etag = dest_storage.update(item, dest_list[uid])
            status[uid] = (source_etag, dest_etag) if source == 'a' else (dest_etag, source_etag)
        elif action == 'delete':
            if dest is not None:
                dest_storage.delete(uid, dest_list[uid])
            del status[uid]

def get_actions(list_a, list_b, status):
    prefetch_from_a = []
    prefetch_from_b = []
    actions = []
    for uid in set(list_a).union(set(list_b)).union(set(status)):
        if uid not in status:
            if uid in list_a and uid in list_b:  # missing status
                # TODO: might need some kind of diffing too?
                status[uid] = (list_a[uid], list_b[uid])
            elif uid in list_a and uid not in list_b:  # new item was created in a
                prefetch_from_a.append(uid)
                actions.append(('upload', uid, 'a', 'b'))
            elif uid not in list_a and uid in list_b:  # new item was created in b
                prefetch_from_b.append(uid)
                actions.append(('upload', uid, 'b', 'a'))
        else:
            if uid in list_a and uid in list_b:
                if list_a[uid] != status[uid][0] and list_b[uid] != status[uid][1]:
                    1/0  # conflict resolution TODO
                elif list_a[uid] != status[uid][0]:  # item was updated in a
                    prefetch_from_a.append(uid)
                    actions.append(('update', uid, 'a', 'b'))
                elif list_b[uid] != status[uid][1]:  # item was updated in b
                    prefetch_from_b.append(uid)
                    actions.append(('update', uid, 'b', 'a'))
                else:  # completely in sync!
                    pass
            elif uid in list_a and uid not in list_b:  # was deleted from b
                actions.append(('delete', uid, None, 'a'))
            elif uid not in list_a and uid in list_b:  # was deleted from a
                actions.append(('delete', uid, None, 'b'))
            elif uid not in list_a and uid not in list_b:  # was deleted from a and b
                actions.append(('delete', uid, None, None))
    return actions, prefetch_from_a, prefetch_from_b