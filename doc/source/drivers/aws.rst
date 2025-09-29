:orphan:

.. attr:: provider[aws]
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

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: iops
         :type: int

      .. attr:: public-ipv4
         :type: bool

      .. attr:: public-ipv6
         :type: bool

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: flavors
      :type: dict

      A list of flavors associated with this provider.

      .. attr:: dedicated-host
         :type: bool

      .. attr:: description
         :type: str

      .. attr:: ebs-optimized
         :type: bool

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

      .. attr:: fleet
         :type: dict

         .. attr:: allocation-strategy

            .. value:: prioritized

            .. value:: price-capacity-optimized

            .. value:: capacity-optimized

            .. value:: diversified

            .. value:: lowest-price

         .. attr:: instance-types
            :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: instance-type
         :type: str

      .. attr:: iops
         :type: int

      .. attr:: market-type

         .. value:: on-demand

         .. value:: spot

      .. attr:: name
         :type: str

      .. attr:: public-ipv4
         :type: bool

      .. attr:: public-ipv6
         :type: bool

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: image-defaults
      :type: dict

      .. attr:: architecture
         :type: str

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: ena-support
         :type: bool

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

      .. attr:: image-format

         .. value:: ova

         .. value:: vhd

         .. value:: vhdx

         .. value:: vmdk

         .. value:: raw

         .. value:: snapshot

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: imds-support

         .. value:: v2.0

         .. value:: null

      .. attr:: import-method

         .. value:: snapshot

         .. value:: image

         .. value:: ebs-direct

      .. attr:: import-timeout
         :type: int

      .. attr:: iops
         :type: int

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: throughput
         :type: int

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

      .. attr:: volume-type
         :type: str

   .. attr:: images
      :type: list

      A list of images associated with this provider.

   .. attr:: images[cloud]
      :type: dict

      These are the attributes available for a Cloud image.

      .. attr:: branch
         :type: str

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

      .. attr:: image-filters
         :type: dict

         .. attr:: name
            :type: str

         .. attr:: values
            :type: str

      .. attr:: image-id
         :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: import-timeout
         :type: int

      .. attr:: iops
         :type: int

      .. attr:: name
         :type: str

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: throughput
         :type: int

      .. attr:: type

         .. value:: cloud

      .. attr:: userdata
         :type: str

      .. attr:: username
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: images[zuul]
      :type: dict

      These are the attributes available for a Zuul image.

      .. attr:: architecture
         :type: str

      .. attr:: branch
         :type: str

      .. attr:: connection-port
         :type: int

      .. attr:: connection-type
         :type: str

      .. attr:: description
         :type: str

      .. attr:: ena-support
         :type: bool

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

      .. attr:: image-format

         .. value:: ova

         .. value:: vhd

         .. value:: vhdx

         .. value:: vmdk

         .. value:: raw

         .. value:: snapshot

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: imds-support

         .. value:: v2.0

         .. value:: null

      .. attr:: import-method

         .. value:: snapshot

         .. value:: image

         .. value:: ebs-direct

      .. attr:: import-timeout
         :type: int

      .. attr:: iops
         :type: int

      .. attr:: name
         :type: str

      .. attr:: python-path
         :type: str

      .. attr:: shell-type
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: throughput
         :type: int

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

      .. attr:: volume-type
         :type: str

   .. attr:: label-defaults
      :type: dict

      .. attr:: az
         :type: str

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

      .. attr:: iam-instance-profile
         :type: dict

         .. attr:: arn
            :type: str

         .. attr:: name
            :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: iops
         :type: int

      .. attr:: key-name
         :type: str

      .. attr:: kms-key-id
         :type: str

      .. attr:: max-age
         :type: int

         The time (in seconds) since creation that a node may be
         available for use.  Ready nodes older than this time will be
         deleted.

      .. attr:: max-ready-age
         :type: int

         The time (in seconds) an unassigned node should stay in ready state.

      .. attr:: reuse
         :type: bool

         Should the node be reused (True) or deleted (False) after use.

      .. attr:: security-group-ids
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

      .. attr:: subnet-ids
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: labels
      :type: dict

      .. attr:: az
         :type: str

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

      .. attr:: iam-instance-profile
         :type: dict

         .. attr:: arn
            :type: str

         .. attr:: name
            :type: str

      .. attr:: image
         :type: str

      .. attr:: imds-http-tokens

         .. value:: optional

         .. value:: required

      .. attr:: iops
         :type: int

      .. attr:: key-name
         :type: str

      .. attr:: kms-key-id
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

      .. attr:: reuse
         :type: bool

         Should the node be reused (True) or deleted (False) after use.

      .. attr:: security-group-ids
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

      .. attr:: subnet-ids
         :type: str

      .. attr:: tags
         :type: dict

      .. attr:: throughput
         :type: int

      .. attr:: userdata
         :type: str

      .. attr:: volume-size
         :type: int

      .. attr:: volume-type
         :type: str

   .. attr:: launch-attempts
      :type: int

   .. attr:: launch-timeout
      :type: int

   .. attr:: name
      :type: str

   .. attr:: object-storage
      :type: dict

      .. attr:: bucket-name
         :type: str

   .. attr:: parent
      :type: str

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

   .. attr:: section
      :type: str


