:orphan:

.. attr:: provider[openstack]
   :type: dict

   .. attr:: abstract
      :type: bool

   .. attr:: connection
      :type: str

   .. attr:: flavor-defaults
      :type: dict

      .. attr:: final

         Whether the configuration of the flavor may be updated
         by values in flavor-defaults or overidden with a new definition
         by sections or providers lower in the hierarchy than the point
         at which the final attribute is applied.

         .. value:: True

            The flavor may not be updated or overidden.

         .. value:: False

            The flavor may be updated or overidden.

         .. value:: allow-override

            The flavor may not be updated by flavor-defaults
            but may be explicitly overidden by redefining
            it in a new 'flavor' entry.

      .. attr:: public-ipv4
         :type: bool

      .. attr:: public-ipv6
         :type: bool

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

   .. attr:: flavors
      :type: dict

      A list of flavors associated with this provider.

      .. attr:: description
         :type: str

      .. attr:: final

         Whether the configuration of the flavor may be updated
         by values in flavor-defaults or overidden with a new definition
         by sections or providers lower in the hierarchy than the point
         at which the final attribute is applied.

         .. value:: True

            The flavor may not be updated or overidden.

         .. value:: False

            The flavor may be updated or overidden.

         .. value:: allow-override

            The flavor may not be updated by flavor-defaults
            but may be explicitly overidden by redefining
            it in a new 'flavor' entry.

      .. attr:: flavor-name
         :type: str

      .. attr:: name
         :type: str

      .. attr:: public-ipv4
         :type: bool

      .. attr:: public-ipv6
         :type: bool

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

   .. attr:: floating-ip-cleanup
      :type: bool

   .. attr:: image-defaults
      :type: dict

      .. attr:: config-drive
         :type: bool

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: final

         Whether the configuration of the label may be updated
         by values in label-defaults or overidden with a new definition
         by sections or providers lower in the hierarchy than the point
         at which the final attribute is applied.

         .. value:: True

            The label may not be updated or overidden.

         .. value:: False

            The label may be updated or overidden.

         .. value:: allow-override

            The label may not be updated by label-defaults
            but may be explicitly overidden by redefining
            it in a new 'label' entry.

      .. attr:: import-timeout
         :type: int

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: upload-methods
         :type: list

         .. value:: copy

         .. value:: import

         .. value:: upload

      .. attr:: userdata
         :type: str

      .. attr:: username
         :type: str

      .. attr:: volume-size
         :type: int

   .. attr:: images
      :type: list

      A list of images associated with this provider.

   .. attr:: images[cloud]
      :type: dict

      These are the attributes available for a Cloud image.

      .. attr:: branch
         :type: str

      .. attr:: config-drive
         :type: bool

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: description
         :type: str

      .. attr:: final

         Whether the configuration of the label may be updated
         by values in label-defaults or overidden with a new definition
         by sections or providers lower in the hierarchy than the point
         at which the final attribute is applied.

         .. value:: True

            The label may not be updated or overidden.

         .. value:: False

            The label may be updated or overidden.

         .. value:: allow-override

            The label may not be updated by label-defaults
            but may be explicitly overidden by redefining
            it in a new 'label' entry.

      .. attr:: image-id
         :type: str

      .. attr:: import-timeout
         :type: int

      .. attr:: name
         :type: str

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: type

         .. value:: cloud

      .. attr:: userdata
         :type: str

      .. attr:: username
         :type: str

      .. attr:: volume-size
         :type: int

   .. attr:: images[zuul]
      :type: dict

      These are the attributes available for a Zuul image.

      .. attr:: branch
         :type: str

      .. attr:: config-drive
         :type: bool

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: description
         :type: str

      .. attr:: final

         Whether the configuration of the label may be updated
         by values in label-defaults or overidden with a new definition
         by sections or providers lower in the hierarchy than the point
         at which the final attribute is applied.

         .. value:: True

            The label may not be updated or overidden.

         .. value:: False

            The label may be updated or overidden.

         .. value:: allow-override

            The label may not be updated by label-defaults
            but may be explicitly overidden by redefining
            it in a new 'label' entry.

      .. attr:: import-timeout
         :type: int

      .. attr:: name
         :type: str

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: type

         .. value:: zuul

      .. attr:: upload-methods
         :type: list

         .. value:: copy

         .. value:: import

         .. value:: upload

      .. attr:: userdata
         :type: str

      .. attr:: username
         :type: str

      .. attr:: volume-size
         :type: int

   .. attr:: label-defaults
      :type: dict

      .. attr:: auto-floating-ip
         :type: bool

      .. attr:: az
         :type: str

      .. attr:: boot-from-volume
         :type: bool

      .. attr:: boot-timeout
         :type: int

         The time (in seconds) to wait for a node to boot.

      .. attr:: executor-zone
         :type: str

         Specify that a Zuul executor in the specified zone is
         used to run jobs with nodes from this label.

      .. attr:: final

         Whether the configuration of the label may be updated
         by values in label-defaults or overidden with a new definition
         by sections or providers lower in the hierarchy than the point
         at which the final attribute is applied.

         .. value:: True

            The label may not be updated or overidden.

         .. value:: False

            The label may be updated or overidden.

         .. value:: allow-override

            The label may not be updated by label-defaults
            but may be explicitly overidden by redefining
            it in a new 'label' entry.

      .. attr:: host-key-checking
         :type: bool

      .. attr:: key-name
         :type: str

      .. attr:: max-age
         :type: int

         The time (in seconds) since creation that a node may be
         available for use.  Ready nodes older than this time will be
         deleted.

      .. attr:: max-ready-age
         :type: int

         The time (in seconds) an unassigned node should stay in ready state.

      .. attr:: networks
         :type: str

         The OpenStack networks to associate with the node.

      .. attr:: reuse
         :type: bool

         Should the node be reused (True) or deleted (False) after use.

      .. attr:: security-groups
         :type: str

      .. attr:: slots
         :type: int

         How many jobs are permitted run on the same node simultaneously.

      .. attr:: snapshot-expiration
         :type: int

         The time (in seconds) until a snapshot expires.

      .. attr:: snapshot-timeout
         :type: int

         The time (in seconds) to wait for a snapshot to complete.

      .. attr:: tags
         :type: dict

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

   .. attr:: labels
      :type: dict

      .. attr:: auto-floating-ip
         :type: bool

      .. attr:: az
         :type: str

      .. attr:: boot-from-volume
         :type: bool

      .. attr:: boot-timeout
         :type: int

         The time (in seconds) to wait for a node to boot.

      .. attr:: description
         :type: str

      .. attr:: executor-zone
         :type: str

         Specify that a Zuul executor in the specified zone is
         used to run jobs with nodes from this label.

      .. attr:: final

         Whether the configuration of the label may be updated
         by values in label-defaults or overidden with a new definition
         by sections or providers lower in the hierarchy than the point
         at which the final attribute is applied.

         .. value:: True

            The label may not be updated or overidden.

         .. value:: False

            The label may be updated or overidden.

         .. value:: allow-override

            The label may not be updated by label-defaults
            but may be explicitly overidden by redefining
            it in a new 'label' entry.

      .. attr:: flavor
         :type: str

      .. attr:: host-key-checking
         :type: bool

      .. attr:: image
         :type: str

      .. attr:: key-name
         :type: str

      .. attr:: max-age
         :type: int

         The time (in seconds) since creation that a node may be
         available for use.  Ready nodes older than this time will be
         deleted.

      .. attr:: max-ready-age
         :type: int

         The time (in seconds) an unassigned node should stay in ready state.

      .. attr:: min-ready
         :type: int

      .. attr:: name
         :type: str

      .. attr:: networks
         :type: str

         The OpenStack networks to associate with the node.

      .. attr:: reuse
         :type: bool

         Should the node be reused (True) or deleted (False) after use.

      .. attr:: security-groups
         :type: str

      .. attr:: slots
         :type: int

         How many jobs are permitted run on the same node simultaneously.

      .. attr:: snapshot-expiration
         :type: int

         The time (in seconds) until a snapshot expires.

      .. attr:: snapshot-timeout
         :type: int

         The time (in seconds) to wait for a snapshot to complete.

      .. attr:: tags
         :type: dict

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

   .. attr:: launch-attempts
      :type: int

   .. attr:: launch-timeout
      :type: int

   .. attr:: name
      :type: str

   .. attr:: parent
      :type: str

   .. attr:: port-cleanup-interval
      :type: int

   .. attr:: region
      :type: str

   .. attr:: resource-limits
      :type: dict

      .. attr:: cores
         :type: int

      .. attr:: instances
         :type: int

      .. attr:: ram
         :type: int

      .. attr:: volume-gb
         :type: int

      .. attr:: volumes
         :type: int

   .. attr:: section
      :type: str


