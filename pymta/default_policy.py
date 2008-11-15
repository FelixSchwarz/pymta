# -*- coding: UTF-8 -*-

__all__ = ['DefaultMTAPolicy']


class DefaultMTAPolicy(object):
    """This is the default policy which just accepts everything."""
    
    def accept_new_connection(self, remote_ip_string, remote_port):
        return True



