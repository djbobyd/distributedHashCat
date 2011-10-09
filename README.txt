This is extensionto the distributed code. It is specifically tuned for using with HashCat 


Original Author of distributed code:
README for Python code for distributed computing
Joshua Stough
Washington and Lee University
2011

 License: This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or (at your
 option) any later version. This program is distributed in the hope that it
 will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 Public License for more details.

Most of the original code is already replaced. The system is much more complex 
but more specific for use only with hashcat. REST server has been added and now 
the system can accept rest calls over web. Persistence layer has been added in 
case of crashes. All tasks submitted to the server are stored in the database 
and distributed according to their priority. The db file is created on first run.
The server is password protected so only authenticated users can login and send jobs.
The passwords in the config file are encrypted by a random key generated on the 
first start. 
The commands sent through the REST interface have the following syntax:
{"hash":"1654", "imei":"34545","priority":"0"}

Other available REST commands are available in the DHServer file 

For creating the encrypted passwords you can use the Encryption class. It is self
contained and the encrypt function will create the file with the random key if it
does not exist and will also encrypt the given string.  




