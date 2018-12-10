from __future__ import division
from __future__ import absolute_import
from pathlib2 import PurePosixPath, PurePath
import logging

class FileSystem(object):
    def __init__(self, files):
        self.root = files

    def resolveTraversal(self, path):
        path = PurePosixPath(path)

        if not path.is_absolute():
            return path

        new_path = []
        for node in path.parts:
            if node == '.':
                pass
            elif node == '..':
                if len(new_path)>1:
                    new_path.pop()
            else:
                new_path.append(node)

        return PurePosixPath(*new_path)

    def get(self, path, root=None):
        if isinstance(path,str) or isinstance(path,unicode):
            path = PurePosixPath(path)

        if isinstance(path,PurePath):
            path = list(path.parts[1:] if path.is_absolute() else path.parts)

        if root is None:
            root = self.root

        if not isinstance(root,dict):
            root = {'?file':True,'?content':root}

        if not path: # Check if reached the final location
            return root
        
        next_node = path[0]
        path.pop(0)

        if '?' in next_node:
            return None
        elif next_node in root:
            if not isinstance(root[next_node],dict):
                root[next_node] = {'?file':True,'?content':root[next_node]}

            root[next_node]['?parent'] = root
            return self.get(path, root[next_node])
        else:
            return None

    def getFile(self, path, root=None):
        node = self.get(path, root)

        if node.get('?file'):
            return node.get('?content')
        else:
            return None

    def getDir(self, path, root=None):
        node = self.get(path, root)

        if isinstance(node,dict) and not node.get('?file'):
            return node
        else:
            return None

    def getMeta(self, path, root=None):
        # Default Meta
        meta = {
            'file':False,
            'dir':False,
            'perms':0000,
            'owner':'0',
            'group':'0',
            'date':'Jan 30  2011',
        }

        # Node for which the meta is collected
        node = self.get(path, root)

        # Find inherited meta
        parents = []
        cur_node = node
        while cur_node:
            parents.insert(0,cur_node)
            cur_node = cur_node.get('?parent')

        for node in parents:
            meta['perms'] = node.get('?perms',meta['perms'])
            meta['owner'] = node.get('?owner',meta['owner'])
            meta['group'] = node.get('?group',meta['group'])
            meta['date'] = node.get('?date',meta['date'])

        # Generate file related meta        
        if self.isFile(path, root):
            meta['file'] = True
            meta['size'] = len(node.get('?content',''))
            meta['links'] = 1

        # Generate dir related meta        
        elif self.isDir(path, root):
            meta['dir'] = True
            meta['size'] = 4096
            meta['links'] = len(self.getDir(path, root))


        # Generate string version of permissions
        perms = meta['perms']
        out = []
        for i in range(0,9):
            out.append('rwx'[i%3] if perms&(1<<(8-i)) else '-')
        meta['perms_str'] = ''.join(out)

        return meta


    def isFile(self, path, root=None):
        return self.getFile(path, root) is not None

    def isDir(self, path, root=None):
        return self.getDir(path, root) is not None
    
    def exists(self, path, root=None):
        return self.get(path, root) is not None

    def resolve(self, path_cur, path_next, path_home):
        path_cur = PurePosixPath(path_cur)
        path_next = PurePosixPath(path_next)


        path_next_parts = path_next.parts
        if not path_next_parts:
            return None

        path_new = None

        if path_next.is_absolute():
            path_new = path_next
        elif path_next_parts[0] == '~':
            path_new = PurePosixPath(path_home)/PurePosixPath(*path_next_parts[1:])
        else:
            path_new = path_cur / path_next
        
        path_new = self.resolveTraversal(path_new)

        if not self.get(path_new) is None:
            return str(path_new)
        else:
            return None

    def list(self, path):
        out = ''
        root = self.getDir(path)
        if not root:
            return ''

        for file_name in root:
            if '?' in file_name:
                continue

            file_meta = self.getMeta(file_name, root)

            file_type = '-'
            if file_meta['dir']:
                file_type = 'd'

            #out += '{file_type}{file_perms}   22 0        0            4096 Jan 30  2011 {file_name}\n'.format(
            out += '{type}{perms} {links:>4d} {owner:<8s} {group:<8s} {size:>8d} {date:<8s} {name}\n'.format(
                type=file_type,
                perms=file_meta['perms_str'],
                links=file_meta['links'],
                owner=file_meta['owner'],
                group=file_meta['group'],
                name=file_name,
                date=file_meta['date'],
                size=file_meta['size'])
            
        logging.info('\n'+out)
        return out

