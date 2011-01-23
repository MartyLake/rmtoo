#
# rmtoo
#   Free and Open Source Requirements Management Tool
#
# Requirement class itself
#
# (c) 2010-2011 by flonatel
#
# For licencing details see COPYING
#

import os
import time
import operator

from rmtoo.lib.storagebackend.txtfile.TxtRecord import TxtRecord
from rmtoo.lib.digraph.Digraph import Digraph
from rmtoo.lib.RMTException import RMTException
from rmtoo.lib.MemLogStore import MemLogStore

class Requirement(Digraph.Node):

    # Requirment Type
    # Each requirement has exactly one type.
    # The class ReqType sets this from the contents of the file.
    # Note: There can only be one (master requirement)
    rt_master_requirement = 1
    # Initial requirement is deprecated
    rt_initial_requirement = 2
    rt_design_decision = 3
    rt_requirement = 4

    # Status Type
    # Each requirement has a Status.
    # It will be read in and set by the ReqStatus class.
    # The status must be one of the following:
    st_not_done = 1
    st_finished = 2

    # Class Type
    # This specifies, if this node is really a node or if this can /
    # must be elaborated in more detail.
    ct_implementable = 1
    ct_detailable = 2

    # Error Status of Requirement
    # (i.e. is the requirment usable?)
    er_fine = 0
    er_error = 1

    def internal_init(self, rid, mls, mods, opts, config):
        Digraph.Node.__init__(self, rid)
        # This are the original tags - when there is no
        # need to convert them to specific values, they are left
        # here.
        self.otags = {}
        # This is the list of converted values.
        self.values = {}
        self.id = rid
        self.mls = mls
        self.mods = mods
        self.opts = opts
        self.config = config

        # The analytic modules store the results in this map:
        self.analytics = {}

        self.state = self.er_fine

    def __init__(self, fd, rid, mls, mods, opts, config):
        self.internal_init(rid, mls, mods, opts, config)
        if fd!=None:
            self.input(fd)

    def input(self, fd):
        # Read it in from the file (Syntactic input)
        req_record = TxtRecord.from_fd(fd, self.id,
                                 self.config.txtio["requirements"])
        req = req_record.get_dict()
        if req == None:
            self.state = self.er_error
            self.mls.error(42, "parser returned error", self.id)
            return

        # Handle all the modules (Semantic input)
        self.handle_modules_reqtag(req)

        # Do not check for remaining tags here. There must be some
        # left over: all those that work on the whole requirement set
        # (e.g. 'Depends on').

        # If everything's fine, store the rest of the req for later
        # inspection.
        self.req = req

    def handle_modules_reqtag(self, reqs):
        for modkey, module in self.mods.reqtag.items():
            try:
                key, value = module.rewrite(self.id, reqs)
                # Check if there is already a key with the current key
                # in the map.
                if key in self.values:
                    self.mls.error(54, "tag '%s' already defined" %
                          (key), self.id)
                    self.state = self.er_error
                    # Also continue to get possible further error
                    # messages.
                self.values[key] = value
            except RMTException, rmte:
                # Some sematic error occured: do not interpret key or
                # value.
                self.mls.error_from_rmte(rmte)
                self.mls.error(41, "semantic error occured in "
                               "module '%s'" % modkey, self.id)
                #print("+++ root cause is: '%s'" % rmte)
                self.state = self.er_error
                # Continue (do not return immeditely) to get also
                # possible other errors.

    def ok(self):
        return self.state==self.er_fine

### Looks that these functions are not used at all

    # Error is an error (no distinct syntax error)
#    def mark_syntax_error(self):
#        self.state = self.er_error

    # Error is an error (no distinct sematic error)
#    def mark_sematic_error(self):
#        self.state = self.er_error

    def get_prio(self):
        return self.values["Priority"]

    def is_open(self):
        return self.values["Status"] == self.st_not_done

    def is_implementable(self):
        return self.values["Class"] == self.ct_implementable

    def get_value(self, key):
        return self.values[key]

    def is_value_available(self, key):
        return key in self.values

    def is_val_av_and_not_null(self, key):
        return key in self.values \
            and self.get_value(key)!=None

    def set_value(self, key, value):
        self.values[key] = value

    # Write out the analytics results.
    def write_analytics_result(self, mstderr):
        for k, v in sorted(self.analytics.items(),
                           key=operator.itemgetter(0)):
            if v[0]<0:
                mstderr.write("+++ Error:Analytics:%s:%s:result is '%+3d'\n"
                              % (k, self.id, v[0]))
                for l in v[1]:
                    mstderr.write("+++ Error:Analytics:%s:%s:%s\n" % 
                                  (k, self.id, l))

    # The following functions are declared internal because they are
    # for internal use only.
    # To copy a requirement (functionally deep copy) two phases are
    # needed: First copy the requirements themselfs then adapt the
    # incoming and outgoing lists to the new requirements.

    # internal copy phase 1
    # Create a deep copy without all requirements (incoming and
    # outgoing) which are not part of one of the given topics.
    # The reqs_included set is a set of pointers to the old
    # requirements. 
    def internal_copy_phase1(self, topic_name_list):
        # Create the new Requirement itself.
        r = Requirement(None, self.id, self.mls, self.mods,
                        self.opts, self.config)
        r.otags = self.otags
        r.values = self.values

        # The only things to copy over are the incoming and the
        # outgoing lists.
        # These are pointers to the old ones!!!
        for req in self.incoming:
            if req.values["Topic"] in topic_name_list:
                r.incoming.append(req)
        for req in self.outgoing:
            if req.values["Topic"] in topic_name_list:
                r.outgoing.append(req)

        return r

    # Adapt the incoming and outgoing list: given a dictionary to map
    # from old to new.
    def internal_copy_phase2(self, old2new):
        outgoing = []
        for o in self.outgoing:
            outgoing.append(old2new[o])
        self.outgoing = outgoing

        incoming = []
        for o in self.incoming:
            incoming.append(old2new[o])
        self.incoming = incoming
        
